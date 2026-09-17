class OrderCannotBeCancelled(Exception):
    def __init__(self, order_id: int) -> None:
        self.order_id = order_id

    def __str__(self) -> str:
        return f"order={self.order_id} cannot be cancelled"
