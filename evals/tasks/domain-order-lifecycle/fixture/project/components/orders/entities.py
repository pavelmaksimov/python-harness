"""Order record: a plain data holder with dict-based storage helpers."""

from dataclasses import dataclass, field

from project.container import Container


@dataclass
class Order:
    order_id: int
    customer_id: int
    status: str = "NEW"
    items: list[dict] = field(default_factory=list)
    discount_percent: int = 0

    def save(self) -> None:
        Container().order_repository.save(self)

    def load(order_id: int) -> "Order":
        return Container().order_repository.get(order_id)
