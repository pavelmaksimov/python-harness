"""Order logic kept as a service over a dict of dicts."""

from project.components.orders.exceptions import OrderCannotBeCancelled


class OrderService:
    def __init__(self) -> None:
        self._orders: dict[int, dict] = {}

    def create(self, order_id: int, items: list[dict], discount_percent: int = 0) -> dict:
        self._orders[order_id] = {
            "id": order_id,
            "status": "NEW",
            "items": items,
            "discount_percent": discount_percent,
        }
        return self._orders[order_id]

    def amount_due(self, order_id: int) -> float:
        order = self._orders[order_id]
        subtotal = sum(item["price"] * item["qty"] for item in order["items"])
        discounted = subtotal * (1 - order["discount_percent"] / 100)
        return round(discounted * 1.2, 2)

    def status_of(self, order_id: int) -> str:
        return self._orders[order_id]["status"]

    def cancel(self, order_id: int) -> None:
        if self._orders[order_id]["status"] != "NEW":
            raise OrderCannotBeCancelled(order_id)
        self._orders[order_id]["status"] = "CANCELLED"

    def pay(self, order_id: int) -> None:
        if self._orders[order_id]["status"] != "NEW":
            raise OrderCannotBeCancelled(order_id)
        self._orders[order_id]["status"] = "PAID"
