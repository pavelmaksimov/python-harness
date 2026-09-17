"""Order cache with raw Redis keys and raw JSON."""

import json

import redis

from project.settings import Settings

_redis = redis.asyncio.Redis(
    host=Settings().REDIS_HOST or "localhost",
    port=Settings().REDIS_PORT,
    db=Settings().REDIS_DB,
)


class OrderCacheRepository:
    async def save(self, order_id: int, data: dict) -> None:
        await _redis.set(f"order:{order_id}", json.dumps(data))

    async def get(self, order_id: int) -> dict | None:
        raw = await _redis.get(f"order:{order_id}")
        if raw is None:
            return None
        return json.loads(raw)

    async def delete(self, order_id: int) -> None:
        await _redis.delete(f"order:{order_id}")
