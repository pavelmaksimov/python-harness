"""Order placement: prices the order and quotes shipping over HTTP."""

import datetime as dt

import httpx

from project.components.orders.schemas import OrderRequestSchema
from project.settings import Settings

QUOTE_TTL = dt.timedelta(minutes=30)


class PlaceOrderUseCase:
    async def run(self, request: OrderRequestSchema) -> dict:
        subtotal = sum(row.qty * row.unit_price_cents for row in request.rows)
        discounted = subtotal * (1 - request.discount_percent / 100)
        quote = await self._quote_shipping(request)
        return {
            "customer_id": request.customer_id,
            "total_cents": round(discounted * 1.2),
            "shipping_cents": quote["cents"],
            "status": "NEW",
            "status_expires_at": dt.datetime.now(dt.timezone.utc) + QUOTE_TTL,
        }

    async def _quote_shipping(self, request: OrderRequestSchema) -> dict:
        response = httpx.post(
            f"{Settings().SHIPPING_API_URL}/quotes",
            json=request.model_dump(),
            timeout=10,
        )
        if response.status_code != 200:
            raise RuntimeError(f"shipping quote failed: {response.status_code}")
        return response.json()
