# Retry helper

Copy this module to `project/libs/retry.py` when the package does not already define
`retry_on_exception` / `retry_unless_exception`.

```python
"""Retry wrappers for transient I/O (HTTP, DB, Redis).

``retry_on_exception`` retries listed types; ``retry_unless_exception`` retries everything
except listed types. Sync and async via ``iscoroutinefunction``.

Example::

    @retry_on_exception((ConnectionError, TimeoutError), max_attempts=3, backoff=2)
    async def fetch(self) -> bytes:
        ...

    @retry_unless_exception((NotFoundError, AuthError), max_attempts=3, backoff=2)
    async def cache_get(self, key: str) -> bytes:
        ...
"""

import asyncio
import logging
import time
from functools import wraps
from typing import Callable, Iterable

logger = logging.getLogger(__name__)


def _as_exception_tuple(
    exceptions: type[Exception] | Iterable[type[Exception]],
) -> tuple[type[Exception], ...]:
    if isinstance(exceptions, type):
        return (exceptions,)
    return tuple(exceptions)


def retry_on_exception(
    exceptions: type[Exception] | Iterable[type[Exception]] | None = None,
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 1.0,
    on_retry: Callable[[int, Exception], None] | None = None,
):
    """Retry when one of ``exceptions`` is raised.

    Args:
        exceptions: Type or types to retry. Empty / omitted retries every ``Exception``.
        max_attempts: Attempts including the first.
        delay: Initial sleep between attempts, in seconds.
        backoff: Multiplier applied to ``delay`` after each failed attempt.
        on_retry: Optional callback ``(attempt, exception)`` before each sleep.
    """
    caught = _as_exception_tuple(exceptions) if exceptions else (Exception,)

    def decorator(func):
        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                current_delay = delay
                for attempt in range(1, max_attempts + 1):
                    try:
                        return await func(*args, **kwargs)
                    except caught as e:
                        if attempt == max_attempts:
                            logger.error(
                                "Failed after %s attempts (func=%s): %s: %s",
                                max_attempts,
                                func.__name__,
                                e.__class__.__name__,
                                e,
                            )
                            raise

                        logger.warning(
                            "Retry %s/%s (func=%s) on %s: %s; sleep=%.2fs",
                            attempt,
                            max_attempts,
                            func.__name__,
                            e.__class__.__name__,
                            e,
                            current_delay,
                        )
                        if on_retry is not None:
                            on_retry(attempt, e)

                        await asyncio.sleep(current_delay)
                        current_delay *= backoff

                return None

            return async_wrapper

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            current_delay = delay
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except caught as e:
                    if attempt == max_attempts:
                        logger.error(
                            "Failed after %s attempts (func=%s): %s: %s",
                            max_attempts,
                            func.__name__,
                            e.__class__.__name__,
                            e,
                        )
                        raise

                    logger.warning(
                        "Retry %s/%s (func=%s) on %s: %s; sleep=%.2fs",
                        attempt,
                        max_attempts,
                        func.__name__,
                        e.__class__.__name__,
                        e,
                        current_delay,
                    )
                    if on_retry is not None:
                        on_retry(attempt, e)

                    time.sleep(current_delay)
                    current_delay *= backoff

            return None

        return sync_wrapper

    return decorator


def retry_unless_exception(
    excluded_exceptions: type[Exception] | Iterable[type[Exception]],
    max_attempts: int = 3,
    delay: float = 1.0,
    backoff: float = 1.0,
    on_retry: Callable[[int, Exception], None] | None = None,
):
    """Retry every exception except ``excluded_exceptions`` (those re-raise immediately).

    Args:
        excluded_exceptions: Type or types that must not be retried.
        max_attempts: Attempts including the first, for all other exceptions.
        delay: Initial sleep between attempts, in seconds.
        backoff: Multiplier applied to ``delay`` after each failed attempt.
        on_retry: Optional callback ``(attempt, exception)`` before each sleep.
    """
    excluded = _as_exception_tuple(excluded_exceptions)

    def decorator(func):
        if asyncio.iscoroutinefunction(func):

            @wraps(func)
            async def async_wrapper(*args, **kwargs):
                current_delay = delay
                for attempt in range(1, max_attempts + 1):
                    try:
                        return await func(*args, **kwargs)
                    except excluded:
                        raise
                    except Exception as e:
                        if attempt == max_attempts:
                            logger.error(
                                "Failed after %s attempts (func=%s): %s: %s",
                                max_attempts,
                                func.__name__,
                                e.__class__.__name__,
                                e,
                            )
                            raise

                        logger.warning(
                            "Retry %s/%s (func=%s) on %s: %s; sleep=%.2fs",
                            attempt,
                            max_attempts,
                            func.__name__,
                            e.__class__.__name__,
                            e,
                            current_delay,
                        )
                        if on_retry is not None:
                            on_retry(attempt, e)

                        await asyncio.sleep(current_delay)
                        current_delay *= backoff

                return None

            return async_wrapper

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            current_delay = delay
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except excluded:
                    raise
                except Exception as e:
                    if attempt == max_attempts:
                        logger.error(
                            "Failed after %s attempts (func=%s): %s: %s",
                            max_attempts,
                            func.__name__,
                            e.__class__.__name__,
                            e,
                        )
                        raise

                    logger.warning(
                        "Retry %s/%s (func=%s) on %s: %s; sleep=%.2fs",
                        attempt,
                        max_attempts,
                        func.__name__,
                        e.__class__.__name__,
                        e,
                        current_delay,
                    )
                    if on_retry is not None:
                        on_retry(attempt, e)

                    time.sleep(current_delay)
                    current_delay *= backoff

            return None

        return sync_wrapper

    return decorator
```
