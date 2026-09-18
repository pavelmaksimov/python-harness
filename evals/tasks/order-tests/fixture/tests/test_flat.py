"""Order tests that grew organically in one flat file."""

import asyncio
from unittest.mock import patch

import pytest

from project.components.orders.schemas import OrderRequestSchema
from project.components.orders.use_cases import PlaceOrderUseCase


@pytest.fixture
def order_payload() -> dict:
    return {
        "customer_id": 1,
        "discount_percent": 10,
        "rows": [
            {
                "sku": "SKU-1",
                "name": "Widget",
                "qty": 2,
                "unit_price_cents": 1500,
                "warehouse": "EU-1",
                "category": "tools",
                "priority": 1,
                "note": "",
            }
        ],
    }


def test_place_order(order_payload):
    with patch.object(PlaceOrderUseCase, "_quote_shipping", return_value={"cents": 500}):
        result = asyncio.run(PlaceOrderUseCase().run(OrderRequestSchema(**order_payload)))
    assert result["status"] == "NEW"


def test_shipping_smoke():
    import httpx

    response = httpx.post(
        "https://shipping.example.com/quotes",
        json={"customer_id": 1},
        timeout=10,
    )
    assert response.status_code == 200


def test_settings_flag(monkeypatch):
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
