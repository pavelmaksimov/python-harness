# Sync HTTP adapter helper

Copy the Python block below to `project/infrastructure/utils/base_client.py` when the service uses
synchronous outbound HTTP. Requires `httpx`, `orjson`, `llm_common`, and the exception classes from
`project/exceptions.py`.

```python
import logging
import time
import typing as t
from contextlib import contextmanager

import httpx
import orjson
from llm_common.prometheus import http_tracking, is_build_metrics

from project.exceptions import ClientError, ExternalApiError, ExternalHTTPConnectionError, ServerError

logger = logging.getLogger(__name__)


class HttpTelemetry:
    def __init__(
        self,
        *,
        name_for_monitoring: str,
        log_level: int | str = logging.INFO,
        logging_extra_data: bool = False,
    ) -> None:
        self.name_for_monitoring = name_for_monitoring
        self.logging_extra_data = logging_extra_data
        if isinstance(log_level, str):
            log_level = logging.getLevelNamesMapping()[log_level.upper()]
        self.log_level = log_level

    def on_request(
        self,
        method: str,
        url: str,
        *,
        headers: dict | None = None,
        params: dict | None = None,
        data: t.Any = None,
        json: t.Any = None,
    ) -> None:
        logger.log(self.log_level, "Call endpoint: %s %s", method, url)
        if not self.logging_extra_data:
            return
        if headers:
            logger.debug("Headers: %s", headers)
        if params:
            logger.debug("Params: %s", params)
        if data:
            logger.debug("Data: %s", data)
        if json:
            logger.debug("Json: %s", json)

    def on_response(self, method: str, url: str, resource: str, response: httpx.Response) -> None:
        duration = response.elapsed.total_seconds()
        logger.debug("End call endpoint: %s %s, duration %s ", method, url, duration)
        self._track(
            resource=resource,
            method=method,
            response_size=int(response.headers.get("content-length", 0)),
            status_code=response.status_code,
            duration=duration,
            request_size=int(response.request.headers.get("content-length", 0)),
        )

    def on_error(
        self,
        method: str,
        url: str,
        resource: str,
        message: str,
        exc: BaseException,
        duration: float,
    ) -> None:
        logger.error("%s: %s %s - %s", message, method, url, exc)
        status_code = 0
        if isinstance(exc, httpx.HTTPStatusError) and exc.response is not None:
            status_code = exc.response.status_code
        self._track(
            resource=resource,
            method=method,
            response_size=0,
            status_code=status_code,
            duration=duration,
            request_size=0,
        )

    def on_response_data(self, response_data: t.Any) -> None:
        if self.logging_extra_data:
            logger.debug("Response data: %s", response_data)

    def _track(
        self,
        *,
        resource: str,
        method: str,
        response_size: int,
        status_code: int,
        duration: float,
        request_size: int,
    ) -> None:
        if not is_build_metrics():
            return
        http_tracking(
            app_type=self.name_for_monitoring,
            resource=resource,
            method=str(method).upper(),
            response_size=response_size,
            status_code=status_code,
            duration=duration,
            request_size=request_size,
        )


class SyncApi:
    ApiError = ExternalApiError
    ServerError = ServerError
    ClientError = ClientError
    ConnectionError = ExternalHTTPConnectionError
    ClientSession = httpx.Client
    name_for_monitoring: str

    def __init__(
        self,
        api_root: str,
        *,
        name_for_monitoring: str,
        headers: dict | None = None,
        request_settings: dict | None = None,
        log_level: int | str = logging.INFO,
        logging_extra_data: bool = False,
    ):
        self.name_for_monitoring = name_for_monitoring
        self.api_root = api_root
        self.request_settings = request_settings or {}
        self.headers = headers or {}
        self.telemetry = HttpTelemetry(
            name_for_monitoring=name_for_monitoring,
            log_level=log_level,
            logging_extra_data=logging_extra_data,
        )
        self.session = None

    @contextmanager
    def Session(self, **session_settings):  # noqa: N802
        if self.session:
            yield self.session
        else:
            try:
                with self.ClientSession(**session_settings) as session:
                    self.session = session
                    yield session
            finally:
                self.session = None

    def call_endpoint(
        self,
        resource: str,
        *,
        method: str = "GET",
        resource_for_monitoring: str | None = None,
        params: dict | None = None,
        headers: dict | None = None,
        data: t.Any = None,
        json: t.Any = None,
        request_settings: dict | None = None,
        session: httpx.Client | None = None,
    ) -> t.Any:
        resource_for_monitoring = resource_for_monitoring or resource
        url = self.api_root
        if resource:
            url = f"{self.api_root}/{resource}"

        headers = self.headers | (headers or {})
        request_settings = self.request_settings | (request_settings or {})

        with session or self.session or self.Session() as sess:
            self.telemetry.on_request(
                method, url, headers=headers, params=params, data=data, json=json
            )
            start_time = time.perf_counter()

            try:
                response = sess.request(
                    method,
                    url,
                    params=params,
                    data=data,
                    json=json,
                    headers=headers,
                    **request_settings,
                )
                self.telemetry.on_response(method, url, resource_for_monitoring, response)
                return self.process_response(response)

            except httpx.ConnectError as exc:
                self.telemetry.on_error(
                    method,
                    url,
                    resource_for_monitoring,
                    "Connection error",
                    exc,
                    time.perf_counter() - start_time,
                )
                raise self.ConnectionError(url=url, method=method, original_error=exc) from exc

            except httpx.TimeoutException as exc:
                self.telemetry.on_error(
                    method,
                    url,
                    resource_for_monitoring,
                    "Timeout error",
                    exc,
                    time.perf_counter() - start_time,
                )
                raise self.ConnectionError(url=url, method=method, original_error=exc) from exc

            except httpx.HTTPStatusError as exc:
                self.telemetry.on_error(
                    method,
                    url,
                    resource_for_monitoring,
                    "HTTP status error",
                    exc,
                    time.perf_counter() - start_time,
                )
                raise self.ConnectionError(url=url, method=method, original_error=exc) from exc

    def response_to_native(self, response: httpx.Response) -> t.Any:
        try:
            return orjson.loads(response.content)
        except ValueError:
            return response.text

    def error_handling(self, response: httpx.Response, response_data: t.Any) -> None:
        if 200 <= response.status_code < 300:
            return

        if 400 <= response.status_code < 500:
            raise self.ClientError(
                response=response,
                response_data=response_data,
                url=response.url,
                status_code=response.status_code,
            )

        if response.status_code >= 500:
            raise self.ServerError(
                response=response,
                response_data=response_data,
                url=response.url,
                status_code=response.status_code,
            )

        raise self.ApiError(response=response, response_data=response_data)

    def process_response(self, response: httpx.Response) -> t.Any:
        response_data = self.response_to_native(response)
        self.telemetry.on_response_data(response_data)
        self.error_handling(response, response_data)
        return response_data


class IClient(t.Protocol):
    ApiError: type[Exception]
    ServerError: type[Exception]
    ClientError: type[Exception]
    ConnectionError: type[Exception]

    Api: t.ClassVar[type[SyncApi]]
    api_root: str
    api: SyncApi
```
