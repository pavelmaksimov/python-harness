"""Order repository with a private engine and a per-call sessionmaker."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine


class OrderRepository:
    async def get_order_sql(self, order_id: int) -> dict | None:
        engine = create_async_engine("postgresql+asyncpg://db/orders", pool_size=5)
        maker = async_sessionmaker(engine, expire_on_commit=False)
        async with maker() as session:
            row = (
                await session.execute(
                    text("SELECT id, status FROM orders WHERE id = :id"),
                    {"id": order_id},
                )
            ).first()
            return dict(row._mapping) if row else None

    async def set_status(self, order_id: int, status: str) -> None:
        engine = create_async_engine("postgresql+asyncpg://db/orders", pool_size=5)
        maker = async_sessionmaker(engine, expire_on_commit=False)
        async with maker() as session:
            await session.execute(
                text("UPDATE orders SET status = :s WHERE id = :id"),
                {"s": status, "id": order_id},
            )
            await session.commit()
