"""In-memory order storage used by the CLI."""


class OrderRepository:
    def __init__(self) -> None:
        self._orders: dict[int, dict] = {
            1: {"id": 1, "status": "NEW"},
            2: {"id": 2, "status": "PAID"},
        }

    async def all(self, status: str | None = None) -> list[dict]:
        orders = list(self._orders.values())
        if status:
            orders = [order for order in orders if order["status"] == status]
        return orders

    async def cancel(self, order_id: int) -> None:
        self._orders[order_id]["status"] = "CANCELLED"
