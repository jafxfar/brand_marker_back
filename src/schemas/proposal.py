from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ProposalAttachmentSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    proposal_id: int
    file_name: str
    file_url: str
    file_type: str


class ProposalSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rfq_id: str
    supplier_actor_id: int
    price: float
    currency: str
    delivery_time: str | None
    message: str | None
    status: str
    created_at: datetime


class ProposalWithRelations(ProposalSchema):
    attachment: ProposalAttachmentSchema | None = None


class ProposalCreate(BaseModel):
    price: float = Field(gt=0)
    currency: str = "RUB"
    delivery_time: str | None = None
    message: str | None = None


class ProposalUpdate(BaseModel):
    price: float | None = Field(default=None, gt=0)
    currency: str | None = None
    delivery_time: str | None = None
    message: str | None = None
