"""Order endpoints, including the login and search routes."""

from fastapi import APIRouter

from project.components.orders.repositories import OrderCacheRepository

router = APIRouter()


@router.get("/orders/{order_id}")
async def get_order(order_id: int) -> dict:
    cached = await OrderCacheRepository().get(order_id)
    if cached is not None:
        return cached
    return {"id": order_id, "status": "NEW"}


@router.get("/orders/search")
async def search_orders(query: str) -> list[dict]:
    return [{"id": 1, "status": "NEW", "query": query}]


@router.post("/login")
async def login(username: str) -> dict:
    return {"username": username, "token": "placeholder"}
