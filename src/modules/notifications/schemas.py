from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PaymentHistoryItem(BaseModel):
    contract_id: int
    milestone_id: int
    title: str
    amount: float
    currency: str
    status: str
    event: str
    created_at: datetime


class PendingPaymentItem(BaseModel):
    contract_id: int
    milestone_id: int
    title: str
    amount: float
    currency: str
    status: str


class ReviewCreate(BaseModel):
    contract_id: int
    target_actor_id: int
    rating: int = Field(ge=1, le=5)
    comment: str | None = None


class ReviewResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contract_id: int
    reviewer_actor_id: int
    target_actor_id: int
    rating: int
    comment: str | None
    created_at: datetime


class NotificationSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    title: str
    body: str
    href: str | None
    read: bool
    created_at: datetime
