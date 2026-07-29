from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PaymentMilestoneSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contract_id: int
    title: str
    percentage: float
    amount: float
    trigger: str
    status: str


class PaymentPlanSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contract_id: int
    payment_type: str
    milestones: list[PaymentMilestoneSchema] = []


class MessageAttachmentSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    message_id: int
    file_name: str
    file_url: str
    file_type: str


class MessageSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    sender_id: int
    text: str
    attachment: MessageAttachmentSchema | None = None
    created_at: datetime | None = None


class ConversationSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contract_id: int
    messages: list[MessageSchema] = []


class ContractFileSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contract_id: int
    file_name: str
    file_url: str
    file_type: str
    uploaded_by: int
    created_at: datetime


class WorkSubmissionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contract_id: int
    type: str
    note: str
    status: str
    submitted_at: datetime
    file_names: list[str]


class ContractSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    rfq_id: str
    proposal_id: int
    buyer_actor_id: int
    supplier_actor_id: int
    title: str
    description: str | None
    agreed_amount: float
    currency: str
    start_date: str
    due_date: str
    payment_type: str
    status: str
    created_at: datetime


class ContractWithRelations(ContractSchema):
    payment_plan: PaymentPlanSchema | None = None
    conversation: ConversationSchema | None = None
    files: list[ContractFileSchema] = []
    submissions: list[WorkSubmissionSchema] = []


class MessageCreate(BaseModel):
    text: str = Field(min_length=1)


class WorkSubmissionCreate(BaseModel):
    type: str = "delivery"
    note: str = ""
    file_names: list[str] = []


class DisputeRequest(BaseModel):
    reason: str = Field(min_length=10)
