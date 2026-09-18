"""Order request schemas — deliberately wide, like the real API payloads."""

from pydantic import BaseModel, Field


class OrderRowSchema(BaseModel):
    sku: str = Field(min_length=3, max_length=32)
    name: str = Field(min_length=1, max_length=128)
    qty: int = Field(ge=0)
    unit_price_cents: int = Field(ge=0)
    warehouse: str = Field(min_length=2, max_length=8)
    category: str = Field(min_length=2, max_length=32)
    priority: int = Field(ge=0, le=5)
    note: str = ""


class OrderRequestSchema(BaseModel):
    customer_id: int
    discount_percent: int = Field(default=0, ge=0, le=100)
    currency: str = Field(default="EUR", min_length=3, max_length=3)
    reference: str = Field(default="", max_length=64)
    rows: list[OrderRowSchema] = Field(min_length=1)
