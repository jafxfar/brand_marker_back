import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class OrderOfferSchema(BaseModel):
    id: str
    order_id: str
    supplier_actor_id: int
    supplier_name: str | None
    price: float
    message: str | None
    delivery_days: int | None
    status: str
    created_at: datetime


class MarketplaceOrderSchema(BaseModel):
    id: str
    buyer_actor_id: int
    kind: str
    title: str
    description: str
    category_id: int | None
    category_label: str | None
    budget: float
    qty: int
    needs_delivery: bool
    status: str
    accepted_offer_id: str | None
    created_at: datetime
    offers: list[OrderOfferSchema] = []


class CreateOrderOfferRequest(BaseModel):
    price: float = Field(gt=0)
    message: str | None = None
    delivery_days: int | None = None


class CreateMarketplaceOrderRequest(BaseModel):
    kind: str
    title: str = Field(min_length=2)
    description: str = ""
    category_id: int | None = None
    category_label: str | None = None
    budget: float = Field(ge=0)
    qty: int = Field(ge=1, default=1)
    needs_delivery: bool = False


class CustomerGroupSchema(BaseModel):
    buyer_actor_id: int
    buyer_name: str
    order_count: int
    total_budget: float
