from project.datatypes import UserIdT


class PlaceOrderUseCase:
    async def run(self, user_id: UserIdT, items: list[dict], discount_percent: int) -> dict:
        # --- pricing buried in the use case -------------------------------
        subtotal = sum(item["price"] * item["qty"] for item in items)
        discounted = subtotal * (1 - discount_percent / 100)
        total = round(discounted * 1.2, 2)  # VAT 20%
        # -------------------------------------------------------------------
        return {"user_id": user_id, "items": items, "total": total, "status": "NEW"}
