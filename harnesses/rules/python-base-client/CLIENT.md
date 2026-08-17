# HTTP adapter helper

Copy this module to `project/infrastructure/utils/base_client.py` when the package does not already
define `AsyncApi` / `SyncApi`. Requires `ClientError`, `ExternalApiError`, `ExternalHTTPConnectionError`,
and `ServerError` from `project/exceptions.py` (`python-exceptions`). Runtime: httpx, orjson.

If `python-monitoring` is installed, HTTP metrics are recorded automatically. `llm_common` is optional —
metric calls are no-ops when the package is missing.

```python
"""Outbound HTTP helper: httpx session reuse, orjson, AppError mapping for adapters."""

import logging
import time
import typing as t
from collections.abc import AsyncIterator, Iterator, Mapping
from contextlib import asynccontextmanager, contextmanager

import httpx
import orjson

from project.exceptions import ClientError, ExternalApiError, ExternalHTTPConnectionError, ServerError

logger = logging.getLogger(__name__)


def _no_metrics() -> bool:
    return False


def _noop_tracking(**_kwargs: t.Any) -> None:
    return None


try:
    from llm_common.prometheus import http_tracking, is_build_metrics
except ImportError:
    is_build_metrics = _no_metrics
    http_tracking = _noop_tracking


def _header_size(headers: Mapping[str, t.Any], name: str = "content-length") -> int:
    try:
        return int(headers.get(name) or 0)
    except (TypeError, ValueError):
        return 0


class _HttpApi:
    ApiError = ExternalApiError
    ServerError = ServerError
    ClientError = ClientError
    ConnectionError = ExternalHTTPConnectionError
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
    ) -> None:
        self.api_root = api_root.rstrip("/")
        self.name_for_monitoring = name_for_monitoring
        self.headers = headers or {}
        self.request_settings = request_settings or {}
        self.logging_extra_data = logging_extra_data
        if isinstance(log_level, str):
            self.log_level = logging.getLevelNamesMapping()[log_level.upper()]
        else:
            self.log_level = log_level
        self.session = None

    def _build_url(self, resource: str) -> str:
        if not resource:
            return self.api_root
        return f"{self.api_root}/{resource.lstrip('/')}"

    def _prepare(
        self,
        resource: str,
        *,
        headers: dict | None,
        request_settings: dict | None,
        params: dict | None,
        data: t.Any,
        json: t.Any,
    ) -> tuple[str, dict[str, t.Any]]:
        url = self._build_url(resource)
        headers = self.headers | (headers or {})
        settings = self.request_settings | (request_settings or {})
        kwargs: dict[str, t.Any] = {"params": params, "headers": headers, **settings}
        if json is not None:
            kwargs["content"] = orjson.dumps(json)
            kwargs["headers"] = {"Content-Type": "application/json"} | headers
            kwargs.pop("json", None)
        elif data is not None:
            kwargs["data"] = data
        return url, kwargs

    def _log_call(
        self,
        method: str,
        url: str,
        *,
        headers: dict | None,
        params: dict | None,
        data: t.Any,
        json: t.Any,
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

    def _track(
        self,
        resource_for_monitoring: str,
        method: str,
        response: httpx.Response | None,
        duration: float,
    ) -> None:
        if not is_build_metrics():
            return
        if response is None:
            http_tracking(
                app_type=self.name_for_monitoring,
                resource=resource_for_monitoring,
                method=method,
                status_code=0,
                duration=duration,
                request_size=0,
                response_size=0,
            )
            return
        elapsed = response.elapsed.total_seconds() if response.elapsed is not None else duration
        http_tracking(
            app_type=self.name_for_monitoring,
            resource=resource_for_monitoring,
            method=method,
            status_code=response.status_code,
            duration=elapsed,
            request_size=_header_size(response.request.headers),
            response_size=_header_size(response.headers),
        )

    def response_to_native(self, response: httpx.Response) -> t.Any:
        try:
            return orjson.loads(response.content)
        except ValueError:
            return response.text

    def error_handling(self, response: httpx.Response, response_data: t.Any) -> None:
        status = response.status_code
        if 200 <= status < 300:
            return
        if 400 <= status < 500:
            raise self.ClientError(
                response=response,
                response_data=response_data,
                url=response.url,
                status_code=status,
            )
        if status >= 500:
            raise self.ServerError(
                response=response,
                response_data=response_data,
                url=response.url,
                status_code=status,
            )
        raise self.ApiError(response=response, response_data=response_data)

    def process_response(self, response: httpx.Response) -> t.Any:
        response_data = self.response_to_native(response)
        if self.logging_extra_data:
            logger.debug("Response data: %s", response_data)
        self.error_handling(response, response_data)
        return response_data


class AsyncApi(_HttpApi):
    ClientSession = httpx.AsyncClient
    session: httpx.AsyncClient | None

    @asynccontextmanager
    async def Session(self, **session_settings: t.Any) -> AsyncIterator[httpx.AsyncClient]:  # noqa: N802
        if self.session is not None:
            yield self.session
            return
        async with self.ClientSession(**session_settings) as session:
            self.session = session
            try:
                yield session
            finally:
                self.session = None

    @asynccontextmanager
    async def _using_session(self, session: httpx.AsyncClient | None) -> AsyncIterator[httpx.AsyncClient]:
        if session is not None:
            yield session
        elif self.session is not None:
            yield self.session
        else:
            async with self.Session() as sess:
                yield sess

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
        url, kwargs = self._prepare(
            resource,
            headers=headers,
            request_settings=request_settings,
            params=params,
            data=data,
            json=json,
        )
        method_u = method.upper()
        self._log_call(method_u, url, headers=kwargs.get("headers"), params=params, data=data, json=json)
        start = time.perf_counter()
        try:
            async with self._using_session(session) as client:
                response = await client.request(method_u, url, **kwargs)
            duration = time.perf_counter() - start
            logger.debug("End call endpoint: %s %s, duration %s ", method_u, url, duration)
            self._track(resource_for_monitoring, method_u, response, duration)
            return await self.process_response(response)
        except (httpx.RequestError, TimeoutError) as exc:
            duration = time.perf_counter() - start
            logger.error("Connection error: %s %s - %s", method_u, url, exc)
            self._track(resource_for_monitoring, method_u, None, duration)
            raise self.ConnectionError(url=url, method=method_u, original_error=exc) from exc

    async def response_to_native(self, response: httpx.Response) -> t.Any:
        return super().response_to_native(response)

    async def error_handling(self, response: httpx.Response, response_data: t.Any) -> None:
        super().error_handling(response, response_data)

    async def process_response(self, response: httpx.Response) -> t.Any:
        response_data = await self.response_to_native(response)
        if self.logging_extra_data:
            logger.debug("Response data: %s", response_data)
        await self.error_handling(response, response_data)
        return response_data


class SyncApi(_HttpApi):
    ClientSession = httpx.Client
    session: httpx.Client | None

    @contextmanager
    def Session(self, **session_settings: t.Any) -> Iterator[httpx.Client]:  # noqa: N802
        if self.session is not None:
            yield self.session
            return
        with self.ClientSession(**session_settings) as session:
            self.session = session
            try:
                yield session
            finally:
                self.session = None

    @contextmanager
    def _using_session(self, session: httpx.Client | None) -> Iterator[httpx.Client]:
        if session is not None:
            yield session
        elif self.session is not None:
            yield self.session
        else:
            with self.Session() as sess:
                yield sess

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
        url, kwargs = self._prepare(
            resource,
            headers=headers,
            request_settings=request_settings,
            params=params,
            data=data,
            json=json,
        )
        method_u = method.upper()
        self._log_call(method_u, url, headers=kwargs.get("headers"), params=params, data=data, json=json)
        start = time.perf_counter()
        try:
            with self._using_session(session) as client:
                response = client.request(method_u, url, **kwargs)
            duration = time.perf_counter() - start
            logger.debug("End call endpoint: %s %s, duration %s ", method_u, url, duration)
            self._track(resource_for_monitoring, method_u, response, duration)
            return self.process_response(response)
        except (httpx.RequestError, TimeoutError) as exc:
            duration = time.perf_counter() - start
            logger.error("Connection error: %s %s - %s", method_u, url, exc)
            self._track(resource_for_monitoring, method_u, None, duration)
            raise self.ConnectionError(url=url, method=method_u, original_error=exc) from exc


class IClient(t.Protocol):
    ApiError: type[Exception]
    ServerError: type[Exception]
    ClientError: type[Exception]
    ConnectionError: type[Exception]
    Api: t.ClassVar[type[AsyncApi | SyncApi]]
    api_root: str
    api: AsyncApi | SyncApi
```
