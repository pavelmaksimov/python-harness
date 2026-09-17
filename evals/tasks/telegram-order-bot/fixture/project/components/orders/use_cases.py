"""Order status use case wired by hand from the handler."""

from sqlalchemy.ext.asyncio import AsyncSession


class OrderStatusUseCase:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def run(self, user_id: int) -> str:
        return "no orders yet"
