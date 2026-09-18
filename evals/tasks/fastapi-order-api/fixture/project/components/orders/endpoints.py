"""Order endpoints that translate failures themselves."""

from fastapi import APIRouter, HTTPException

from project.datatypes import UserIdT
from project.exceptions import NotFoundError

router = APIRouter()


def _load_order(order_id: int) -> dict:
    if order_id != 1:
        raise NotFoundError("order", order_id)
    return {"id": order_id, "status": "NEW"}


@router.get("/orders/{order_id}")
def get_order(order_id: UserIdT):
    try:
        return _load_order(order_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception:
        raise HTTPException(status_code=500) from None


@router.post("/orders")
def create_order(payload: dict):
    try:
        return {"id": 1, "payload": payload}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=str(exc)) from exc
