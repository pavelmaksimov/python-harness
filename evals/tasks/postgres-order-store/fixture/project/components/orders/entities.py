"""Order domain model that also persists itself."""

import enum
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from project.datatypes import OrderIdT, UserIdT


class OrderStatus(enum.Enum):
    NEW = "NEW"
    PAID = "PAID"
    CANCELLED = "CANCELLED"


@dataclass(eq=False, slots=True)
class Order:
    id: OrderIdT
    user_id: UserIdT
    status: OrderStatus = OrderStatus.NEW
    payload: dict = field(default_factory=dict)
    created_at: datetime | None = None

    __hash__ = None

    def __eq__(self, other: object) -> bool:
        return isinstance(other, Order) and self.id == other.id

    def pay(self) -> None:
        if self.status is not OrderStatus.NEW:
            raise ValueError(f"cannot pay from {self.status}")
        self.status = OrderStatus.PAID

    async def save(self, session: AsyncSession) -> None:
        session.add(self)
        await session.flush()
