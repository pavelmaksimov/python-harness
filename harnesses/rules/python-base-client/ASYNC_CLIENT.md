# Async HTTP adapter helper

Copy the Python block below to `project/infrastructure/base/http_client.py` when the service uses
asynchronous outbound HTTP. Requires `httpx`, `orjson`, `llm_common`, and the exception classes from
`project/exceptions.py`.

```python
import logging
import time
import typing as t
from contextlib import asynccontextmanager

import httpx
import orjson
from llm_common.prometheus import http_tracking, is_build_metrics

from project.exceptions import ClientError, ExternalApiError, ExternalHTTPConnectionError, ServerError

logger = logging.getLogger(__name__)


class Callback:
    def request_callback(
        self,
        method: str,
        url: str,
        *,
        headers: dict | None = None,
        params: dict | None = None,
        data: t.Any = None,
        json: t.Any = None,
    ) -> None:
        pass

    def response_callback(
        self,
        method: str,
        url: str,
        resource: str,
        response: httpx.Response,
    ) -> None:
        pass

    def error_callback(
        self,
        method: str,
        url: str,
        resource: str,
        message: str,
        exc: BaseException,
        duration: float,
    ) -> None:
        pass

    def response_data_callback(self, response_data: t.Any) -> None:
        pass


class LoggingCallback(Callback):
    def __init__(
        self,
        *,
        log_level: int | str = logging.INFO,
        logging_extra_data: bool = False,
    ) -> None:
        if isinstance(log_level, str):
            log_level = logging.getLevelNamesMapping()[log_level.upper()]
        self.log_level = log_level
        self.logging_extra_data = logging_extra_data

    def request_callback(
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

    def response_callback(
        self,
        method: str,
        url: str,
        resource: str,
        response: httpx.Response,
    ) -> None:
        logger.debug(
            "End call endpoint: %s %s, duration %s ",
            method,
            url,
            response.elapsed.total_seconds(),
        )

    def error_callback(
        self,
        method: str,
        url: str,
        resource: str,
        message: str,
        exc: BaseException,
        duration: float,
    ) -> None:
        logger.error("%s: %s %s - %s", message, method, url, exc)

    def response_data_callback(self, response_data: t.Any) -> None:
        if self.logging_extra_data:
            logger.debug("Response data: %s", response_data)


class TelemetryCallback(Callback):
    def __init__(self, *, name_for_monitoring: str) -> None:
        self.name_for_monitoring = name_for_monitoring

    def response_callback(
        self,
        method: str,
        url: str,
        resource: str,
        response: httpx.Response,
    ) -> None:
        self._track(
            resource=resource,
            method=method,
            response_size=int(response.headers.get("content-length", 0)),
            status_code=response.status_code,
            duration=response.elapsed.total_seconds(),
            request_size=int(response.request.headers.get("content-length", 0)),
        )

    def error_callback(
        self,
        method: str,
        url: str,
        resource: str,
        message: str,
        exc: BaseException,
        duration: float,
    ) -> None:
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


class AsyncApi:
    ApiError = ExternalApiError
    ServerError = ServerError
    ClientError = ClientError
    ConnectionError = ExternalHTTPConnectionError
    ClientSession = httpx.AsyncClient
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
        self.api_root = api_root
        self.name_for_monitoring = name_for_monitoring
        self.request_settings = request_settings or {}
        self.headers = headers or {}
        self.callbacks: list[Callback] = [
            LoggingCallback(log_level=log_level, logging_extra_data=logging_extra_data),
            TelemetryCallback(name_for_monitoring=name_for_monitoring),
        ]
        self.session = None

    def request_callback(self, *args: t.Any, **kwargs: t.Any) -> None:
        for callback in self.callbacks:
            callback.request_callback(*args, **kwargs)

    def response_callback(self, *args: t.Any, **kwargs: t.Any) -> None:
        for callback in self.callbacks:
            callback.response_callback(*args, **kwargs)

    def error_callback(self, *args: t.Any, **kwargs: t.Any) -> None:
        for callback in self.callbacks:
            callback.error_callback(*args, **kwargs)

    def response_data_callback(self, *args: t.Any, **kwargs: t.Any) -> None:
        for callback in self.callbacks:
            callback.response_data_callback(*args, **kwargs)

    @asynccontextmanager
    async def Session(self, **session_settings):  # noqa: N802
        if self.session:
            yield self.session
        else:
            try:
                async with self.ClientSession(**session_settings) as session:
                    self.session = session
                    yield session
            finally:
                self.session = None

    async def call_endpoint(
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
        session: httpx.AsyncClient | None = None,
    ) -> t.Any:
        resource_for_monitoring = resource_for_monitoring or resource
        url = self.api_root
        if resource:
            url = f"{self.api_root}/{resource}"
        headers = self.headers | (headers or {})
        request_settings = self.request_settings | (request_settings or {})

        async with session or self.session or self.Session() as sess:
            self.request_callback(
                method, url, headers=headers, params=params, data=data, json=json
            )
            start_time = time.perf_counter()

            try:
                response = await sess.request(
                    method,
                    url,
                    params=params,
                    data=data,
                    json=json,
                    headers=headers,
                    **request_settings,
                )
                self.response_callback(method, url, resource_for_monitoring, response)
                return self.process_response(response)

            except httpx.ConnectError as exc:
                self.error_callback(
                    method,
                    url,
                    resource_for_monitoring,
                    "Connection error",
                    exc,
                    time.perf_counter() - start_time,
                )
                raise self.ConnectionError(url=url, method=method, original_error=exc) from exc

            except httpx.TimeoutException as exc:
                self.error_callback(
                    method,
                    url,
                    resource_for_monitoring,
                    "Timeout error",
                    exc,
                    time.perf_counter() - start_time,
                )
                raise self.ConnectionError(url=url, method=method, original_error=exc) from exc

            except httpx.HTTPStatusError as exc:
                self.error_callback(
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
        self.response_data_callback(response_data)
        self.error_handling(response, response_data)
        return response_data


class IClient(t.Protocol):
    ApiError: type[Exception]
    ServerError: type[Exception]
    ClientError: type[Exception]
    ConnectionError: type[Exception]

    Api: t.ClassVar[type[AsyncApi]]
    api_root: str
    api: AsyncApi
```
