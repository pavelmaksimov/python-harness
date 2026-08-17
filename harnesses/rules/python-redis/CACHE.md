# Redis cache adapter

Copy this module to `project/infrastructure/adapters/acache.py` when the package does not
already define `redis_client` / `redis_atransaction`. Cache repositories import these helpers;
services and use cases do not open Redis clients.

`Settings` must expose `REDIS_HOST`, `REDIS_PORT`, `REDIS_DB`, and `redis_is_configured()`
(see below).

```python
import contextvars
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import timedelta
from functools import lru_cache
from typing import ClassVar

import redis
from redis.asyncio.client import Pipeline

from project.settings import Settings

redis_async_transactions: contextvars.ContextVar[Pipeline | None] = contextvars.ContextVar(
    "current_transaction",
    default=None,
)


@lru_cache
def redis_client() -> redis.asyncio.Redis:
    host = Settings().REDIS_HOST
    if not host:
        msg = "Redis is not configured: set REDIS_HOST"
        raise RuntimeError(msg)
    return redis.asyncio.Redis(
        host=host,
        port=Settings().REDIS_PORT,
        db=Settings().REDIS_DB,
    )


@asynccontextmanager
async def isolated_redis_atransaction() -> AsyncIterator[Pipeline]:
    """Open a new pipeline; execute it on exit. Does not join an outer transaction."""
    client = redis_client()
    async with client.pipeline() as pipe:
        yield pipe
        await pipe.execute()


@asynccontextmanager
async def redis_atransaction() -> AsyncIterator[Pipeline]:
    """Reuse the ContextVar pipeline, or open one and execute it on exit."""
    current_transaction = redis_async_transactions.get()

    if current_transaction:
        yield current_transaction
    else:
        client = redis_client()
        async with client.pipeline() as pipe:
            token = redis_async_transactions.set(pipe)
            try:
                yield pipe
                await pipe.execute()
            finally:
                redis_async_transactions.reset(token)


class CacheRepository:
    client = redis_client
    key_template: ClassVar[str]
    ttl: ClassVar[timedelta]
```

If `project/components/base/repositories.py` already defines `CacheRepository`, keep that
class and omit the copy above from the adapter module.

## Settings contract

Add these fields and methods to `SettingsValidator` if missing (`python-settings`).

```python
class SettingsValidator(BaseSettings):
    REDIS_HOST: str | None = None
    REDIS_PORT: int = 6379
    REDIS_DB: int = 0

    def redis_is_configured(self) -> bool:
        return bool(self.REDIS_HOST)
```

## Cache repository

Put the subclass in `project/components/{name}/repositories.py`. Cache payload schema in
that component's `schemas.py`.

```python
from datetime import timedelta

import orjson

from project.datatypes import ItemIdT
from project.infrastructure.adapters.acache import CacheRepository, redis_atransaction
from project.components.item.schemas import ItemCacheSchema


class ItemCacheRepository(CacheRepository):
    key_template = "item:{}"
    ttl = timedelta(days=7)

    @classmethod
    async def save(cls, item_id: ItemIdT, data: ItemCacheSchema) -> None:
        async with redis_atransaction() as tr:
            content = orjson.dumps(data.model_dump(exclude_unset=True))
            tr.set(cls.key_template.format(item_id), content, ex=cls.ttl)

    @classmethod
    async def get(cls, item_id: ItemIdT) -> ItemCacheSchema | None:
        content = await cls.client().get(cls.key_template.format(item_id))
        if content is None:
            return None
        return ItemCacheSchema(**orjson.loads(content))

    @classmethod
    async def delete(cls, item_id: ItemIdT) -> None:
        async with redis_atransaction() as tr:
            tr.delete(cls.key_template.format(item_id))
```

## Test fixtures

Copy into `tests/conftest.py` when Redis tests are added (merge; do not overwrite without asking).
After a host override, `cache_clear()` the client factory.

```python
import pytest_asyncio
from testcontainers.redis import AsyncRedisContainer

from project.infrastructure.adapters.acache import redis_client
from project.settings import Settings


@pytest_asyncio.fixture(scope="session")
async def async_init_redis(setup):
    with AsyncRedisContainer("redis") as redis_container:
        client = await redis_container.get_async_client()
        connection_kwargs = client.get_connection_kwargs()
        with Settings.local(
            REDIS_HOST=connection_kwargs["host"],
            REDIS_PORT=int(connection_kwargs["port"]),
            REDIS_DB=int(connection_kwargs["db"]),
        ):
            redis_client.cache_clear()
            yield client
            redis_client.cache_clear()


@pytest_asyncio.fixture
async def async_redis(async_init_redis):
    yield async_init_redis
    await async_init_redis.flushdb()
```
