import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
import uuid

from src.db.base import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UserRole(str, enum.Enum):
    buyer = "buyer"
    supplier = "supplier"
    both = "both"
    admin = "admin"
    superadmin = "superadmin"
    moderator = "moderator"


class UserStatus(str, enum.Enum):
    pending = "pending"
    active = "active"
    blocked = "blocked"


class CompanyRole(str, enum.Enum):
    director = "director"
    admin = "admin"
    moderator = "moderator"
    accountant = "accountant"


class ActorType(str, enum.Enum):
    buyer = "buyer"
    supplier = "supplier"


class ActorKind(str, enum.Enum):
    individual = "individual"
    company = "company"


class TrustLevel(str, enum.Enum):
    basic = "basic"
    standard = "standard"
    verified = "verified"


class VerificationStatus(str, enum.Enum):
    pending = "pending"
    verified = "verified"
    rejected = "rejected"


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    role: Mapped[UserRole] = mapped_column(Enum(UserRole, name="user_role"))
    status: Mapped[UserStatus] = mapped_column(
        Enum(UserStatus, name="user_status"), default=UserStatus.active
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    company_memberships: Mapped[list["CompanyUser"]] = relationship(back_populates="user")
    owned_companies: Mapped[list["Company"]] = relationship(back_populates="owner")
    individual_actors: Mapped[list["Actor"]] = relationship(
        back_populates="user",
        foreign_keys="Actor.user_id",
    )
    notifications: Mapped[list["Notification"]] = relationship(back_populates="user")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="user")


class Actor(Base):
    __tablename__ = "actors"
    __table_args__ = (
        Index(
            "uq_actor_individual_user_side",
            "user_id",
            "side",
            unique=True,
            postgresql_where=text("kind = 'individual'"),
        ),
        Index(
            "uq_actor_company_side",
            "company_id",
            "side",
            unique=True,
            postgresql_where=text("kind = 'company'"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[ActorKind] = mapped_column(Enum(ActorKind, name="actor_kind"))
    side: Mapped[ActorType] = mapped_column(Enum(ActorType, name="actor_side"))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    company_id: Mapped[int | None] = mapped_column(
        ForeignKey("companies.id"), nullable=True, index=True
    )
    display_name: Mapped[str] = mapped_column(String(255))
    trust_level: Mapped[TrustLevel] = mapped_column(
        Enum(TrustLevel, name="trust_level"), default=TrustLevel.basic
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    user: Mapped["User | None"] = relationship(
        back_populates="individual_actors", foreign_keys=[user_id]
    )
    company: Mapped["Company | None"] = relationship(
        back_populates="actors", foreign_keys=[company_id]
    )


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(255))
    actor_type: Mapped[ActorType] = mapped_column(Enum(ActorType, name="actor_type"))
    owner_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    legal_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tax_number: Mapped[str | None] = mapped_column(String(50), nullable=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo: Mapped[str | None] = mapped_column(String(500), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    verification_status: Mapped[VerificationStatus] = mapped_column(
        Enum(VerificationStatus, name="verification_status"), default=VerificationStatus.pending
    )
    rating: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    owner: Mapped["User"] = relationship(back_populates="owned_companies")
    members: Mapped[list["CompanyUser"]] = relationship(back_populates="company")
    profile: Mapped["CompanyProfile | None"] = relationship(back_populates="company", uselist=False)
    stats: Mapped["CompanyStats | None"] = relationship(back_populates="company", uselist=False)
    categories: Mapped[list["CompanyCategory"]] = relationship(back_populates="company")
    certificates: Mapped[list["CompanyCertificate"]] = relationship(back_populates="company")
    actors: Mapped[list["Actor"]] = relationship(
        back_populates="company", foreign_keys="Actor.company_id"
    )


class CompanyUser(Base):
    __tablename__ = "company_users"
    __table_args__ = (UniqueConstraint("company_id", "user_id", name="uq_company_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    role: Mapped[CompanyRole] = mapped_column(Enum(CompanyRole, name="company_role"))

    company: Mapped["Company"] = relationship(back_populates="members")
    user: Mapped["User"] = relationship(back_populates="company_memberships")


class CompanyProfile(Base):
    __tablename__ = "company_profiles"

    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), primary_key=True)
    founded_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    employees_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    annual_revenue_range: Mapped[str | None] = mapped_column(String(100), nullable=True)
    languages: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)
    industries: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)

    company: Mapped["Company"] = relationship(back_populates="profile")


class CompanyStats(Base):
    __tablename__ = "company_stats"

    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), primary_key=True)
    completed_contracts: Mapped[int] = mapped_column(Integer, default=0)
    active_contracts: Mapped[int] = mapped_column(Integer, default=0)
    disputes_count: Mapped[int] = mapped_column(Integer, default=0)
    average_rating: Mapped[float] = mapped_column(Float, default=0.0)

    company: Mapped["Company"] = relationship(back_populates="stats")


class CompanyCategory(Base):
    __tablename__ = "company_categories"
    __table_args__ = (UniqueConstraint("company_id", "category_id", name="uq_company_category"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))

    company: Mapped["Company"] = relationship(back_populates="categories")
    category: Mapped["Category"] = relationship(back_populates="company_links")


class CompanyCertificate(Base):
    __tablename__ = "company_certificates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"))
    title: Mapped[str] = mapped_column(String(255))
    issuer: Mapped[str] = mapped_column(String(255))
    issue_date: Mapped[str] = mapped_column(String(20))
    expiry_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    file_url: Mapped[str] = mapped_column(String(500))

    company: Mapped["Company"] = relationship(back_populates="certificates")


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    parent_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(255))
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True)

    children: Mapped[list["Category"]] = relationship(back_populates="parent")
    parent: Mapped["Category | None"] = relationship(back_populates="children", remote_side=[id])
    company_links: Mapped[list["CompanyCategory"]] = relationship(back_populates="category")


class RfqType(str, enum.Enum):
    product = "product"
    service = "service"


class BudgetType(str, enum.Enum):
    fixed = "fixed"
    range = "range"
    open = "open"


class RfqVisibility(str, enum.Enum):
    public = "public"
    invited_only = "invited_only"


class RfqStatus(str, enum.Enum):
    draft = "draft"
    published = "published"
    receiving_proposals = "receiving_proposals"
    supplier_selected = "supplier_selected"
    contract_created = "contract_created"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"
    expired = "expired"
    disputed = "disputed"


class Rfq(Base):
    __tablename__ = "rfqs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    actor_id: Mapped[int] = mapped_column(ForeignKey("actors.id"), index=True)
    created_by: Mapped[str] = mapped_column(String(255))
    type: Mapped[RfqType] = mapped_column(Enum(RfqType, name="rfq_type"))
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_id: Mapped[str] = mapped_column(String(100))
    budget_type: Mapped[BudgetType] = mapped_column(Enum(BudgetType, name="budget_type"))
    budget_from: Mapped[float | None] = mapped_column(Float, nullable=True)
    budget_to: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(10))
    deadline: Mapped[str] = mapped_column(String(30))
    visibility: Mapped[RfqVisibility] = mapped_column(Enum(RfqVisibility, name="rfq_visibility"))
    status: Mapped[RfqStatus] = mapped_column(
        Enum(RfqStatus, name="rfq_status"), default=RfqStatus.draft
    )
    # Product fields
    quantity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    delivery_country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    delivery_city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    delivery_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    delivery_date: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # Service fields
    project_duration: Mapped[str | None] = mapped_column(String(100), nullable=True)
    start_date: Mapped[str | None] = mapped_column(String(30), nullable=True)
    team_size_required: Mapped[int | None] = mapped_column(Integer, nullable=True)
    experience_required: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )

    actor: Mapped["Actor"] = relationship(foreign_keys=[actor_id])
    attachments: Mapped[list["RfqAttachment"]] = relationship(back_populates="rfq")
    invited_suppliers: Mapped[list["RfqInvitedSupplier"]] = relationship(back_populates="rfq")
    proposals: Mapped[list["Proposal"]] = relationship(back_populates="rfq")
    contracts: Mapped[list["Contract"]] = relationship(back_populates="rfq")


class RfqAttachment(Base):
    __tablename__ = "rfq_attachments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    rfq_id: Mapped[str] = mapped_column(ForeignKey("rfqs.id"))
    file_name: Mapped[str] = mapped_column(String(255))
    file_url: Mapped[str] = mapped_column(String(500))
    file_type: Mapped[str] = mapped_column(String(100))

    rfq: Mapped["Rfq"] = relationship(back_populates="attachments")


class RfqInvitedSupplier(Base):
    __tablename__ = "rfq_invited_suppliers"
    __table_args__ = (
        UniqueConstraint("rfq_id", "supplier_actor_id", name="uq_rfq_supplier"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rfq_id: Mapped[str] = mapped_column(ForeignKey("rfqs.id"))
    supplier_actor_id: Mapped[int] = mapped_column(ForeignKey("actors.id"))

    rfq: Mapped["Rfq"] = relationship(back_populates="invited_suppliers")


class Currency(str, enum.Enum):
    RUB = "RUB"
    USD = "USD"
    EUR = "EUR"
    KZT = "KZT"
    CNY = "CNY"


class ProposalStatus(str, enum.Enum):
    submitted = "submitted"
    viewed = "viewed"
    shortlisted = "shortlisted"
    accepted = "accepted"
    rejected = "rejected"
    withdrawn = "withdrawn"


class Proposal(Base):
    __tablename__ = "proposals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rfq_id: Mapped[str] = mapped_column(ForeignKey("rfqs.id"), index=True)
    supplier_actor_id: Mapped[int] = mapped_column(ForeignKey("actors.id"), index=True)
    price: Mapped[float] = mapped_column(Float)
    currency: Mapped[Currency] = mapped_column(Enum(Currency, name="currency"))
    delivery_time: Mapped[str | None] = mapped_column(String(100), nullable=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ProposalStatus] = mapped_column(
        Enum(ProposalStatus, name="proposal_status"), default=ProposalStatus.submitted
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    rfq: Mapped["Rfq"] = relationship(back_populates="proposals")
    attachment: Mapped["ProposalAttachment | None"] = relationship(
        back_populates="proposal", uselist=False
    )
    contract: Mapped["Contract | None"] = relationship(back_populates="proposal", uselist=False)


class ProposalAttachment(Base):
    __tablename__ = "proposal_attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    proposal_id: Mapped[int] = mapped_column(ForeignKey("proposals.id"), unique=True)
    file_name: Mapped[str] = mapped_column(String(255))
    file_url: Mapped[str] = mapped_column(String(500))
    file_type: Mapped[str] = mapped_column(String(100))

    proposal: Mapped["Proposal"] = relationship(back_populates="attachment")


class PaymentType(str, enum.Enum):
    full_prepayment = "full_prepayment"
    split_payment = "split_payment"
    milestone = "milestone"
    full_postpayment = "full_postpayment"


class ContractStatus(str, enum.Enum):
    pending_payment = "pending_payment"
    active = "active"
    delivered = "delivered"
    completed = "completed"
    cancelled = "cancelled"
    disputed = "disputed"


class Contract(Base):
    __tablename__ = "contracts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    rfq_id: Mapped[str] = mapped_column(ForeignKey("rfqs.id"), index=True)
    proposal_id: Mapped[int] = mapped_column(ForeignKey("proposals.id"), unique=True)
    buyer_actor_id: Mapped[int] = mapped_column(ForeignKey("actors.id"), index=True)
    supplier_actor_id: Mapped[int] = mapped_column(ForeignKey("actors.id"), index=True)
    title: Mapped[str] = mapped_column(String(500))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    agreed_amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[Currency] = mapped_column(Enum(Currency, name="contract_currency", create_constraint=False))
    start_date: Mapped[str] = mapped_column(String(30))
    due_date: Mapped[str] = mapped_column(String(30))
    payment_type: Mapped[PaymentType] = mapped_column(Enum(PaymentType, name="payment_type"))
    status: Mapped[ContractStatus] = mapped_column(
        Enum(ContractStatus, name="contract_status"), default=ContractStatus.pending_payment
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    rfq: Mapped["Rfq"] = relationship(back_populates="contracts")
    proposal: Mapped["Proposal"] = relationship(back_populates="contract")
    payment_plan: Mapped["PaymentPlan | None"] = relationship(back_populates="contract", uselist=False)
    conversation: Mapped["Conversation | None"] = relationship(back_populates="contract", uselist=False)
    files: Mapped[list["ContractFile"]] = relationship(back_populates="contract")
    submissions: Mapped[list["WorkSubmission"]] = relationship(back_populates="contract")


class PaymentMilestoneStatus(str, enum.Enum):
    pending = "pending"
    awaiting_payment = "awaiting_payment"
    funded = "funded"
    in_progress = "in_progress"
    submitted = "submitted"
    approved = "approved"
    released = "released"
    refunded = "refunded"
    disputed = "disputed"
    overdue = "overdue"
    cancelled = "cancelled"


class PaymentMilestoneTrigger(str, enum.Enum):
    contract_signed = "contract_signed"
    delivery_accepted = "delivery_accepted"


class PaymentPlan(Base):
    __tablename__ = "payment_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id"), unique=True)
    payment_type: Mapped[PaymentType] = mapped_column(
        Enum(PaymentType, name="plan_payment_type", create_constraint=False)
    )

    contract: Mapped["Contract"] = relationship(back_populates="payment_plan")
    milestones: Mapped[list["PaymentMilestone"]] = relationship(back_populates="payment_plan")


class PaymentMilestone(Base):
    __tablename__ = "payment_milestones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    payment_plan_id: Mapped[int] = mapped_column(ForeignKey("payment_plans.id"))
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id"), index=True)
    title: Mapped[str] = mapped_column(String(255))
    percentage: Mapped[float] = mapped_column(Float)
    amount: Mapped[float] = mapped_column(Float)
    trigger: Mapped[str] = mapped_column(String(50))
    status: Mapped[PaymentMilestoneStatus] = mapped_column(
        Enum(PaymentMilestoneStatus, name="milestone_status"), default=PaymentMilestoneStatus.pending
    )

    payment_plan: Mapped["PaymentPlan"] = relationship(back_populates="milestones")


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id"), unique=True)

    contract: Mapped["Contract"] = relationship(back_populates="conversation")
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation")


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    conversation_id: Mapped[int] = mapped_column(ForeignKey("conversations.id"))
    sender_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    conversation: Mapped["Conversation"] = relationship(back_populates="messages")
    attachment: Mapped["MessageAttachment | None"] = relationship(back_populates="message", uselist=False)


class MessageAttachment(Base):
    __tablename__ = "message_attachments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("messages.id"), unique=True)
    file_name: Mapped[str] = mapped_column(String(255))
    file_url: Mapped[str] = mapped_column(String(500))
    file_type: Mapped[str] = mapped_column(String(100))

    message: Mapped["Message"] = relationship(back_populates="attachment")


class ContractFile(Base):
    __tablename__ = "contract_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id"))
    file_name: Mapped[str] = mapped_column(String(255))
    file_url: Mapped[str] = mapped_column(String(500))
    file_type: Mapped[str] = mapped_column(String(100))
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    contract: Mapped["Contract"] = relationship(back_populates="files")


class WorkSubmissionStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"


class WorkSubmissionType(str, enum.Enum):
    delivery = "delivery"
    work = "work"


class WorkSubmission(Base):
    __tablename__ = "work_submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id"))
    type: Mapped[WorkSubmissionType] = mapped_column(Enum(WorkSubmissionType, name="submission_type"))
    note: Mapped[str] = mapped_column(Text)
    status: Mapped[WorkSubmissionStatus] = mapped_column(
        Enum(WorkSubmissionStatus, name="submission_status"), default=WorkSubmissionStatus.pending
    )
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    file_names: Mapped[list[str]] = mapped_column(ARRAY(String), default=list)

    contract: Mapped["Contract"] = relationship(back_populates="submissions")


class Review(Base):
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("contract_id", "reviewer_actor_id", name="uq_review_contract"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contract_id: Mapped[int] = mapped_column(ForeignKey("contracts.id"))
    reviewer_actor_id: Mapped[int] = mapped_column(ForeignKey("actors.id"))
    target_actor_id: Mapped[int] = mapped_column(ForeignKey("actors.id"))
    rating: Mapped[int] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    target_actor: Mapped["Actor"] = relationship(foreign_keys=[target_actor_id])


class NotificationType(str, enum.Enum):
    order = "order"
    offer = "offer"
    payment = "payment"
    system = "system"
    rfq = "rfq"
    contract = "contract"
    proposal = "proposal"


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True)
    company_id: Mapped[int | None] = mapped_column(ForeignKey("companies.id"), nullable=True)
    type: Mapped[NotificationType] = mapped_column(Enum(NotificationType, name="notification_type"))
    title: Mapped[str] = mapped_column(String(255))
    body: Mapped[str] = mapped_column(Text)
    href: Mapped[str | None] = mapped_column(String(500), nullable=True)
    read: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped["User"] = relationship(back_populates="notifications")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(100))
    resource_type: Mapped[str] = mapped_column(String(100))
    resource_id: Mapped[str] = mapped_column(String(100))
    details: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped["User | None"] = relationship(back_populates="audit_logs")


class RefreshTokenBlacklist(Base):
    __tablename__ = "refresh_token_blacklist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    token_jti_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class CatalogItemType(str, enum.Enum):
    product = "product"
    service = "service"


class ItemStatus(str, enum.Enum):
    draft = "draft"
    active = "active"
    archived = "archived"


class PricingType(str, enum.Enum):
    fixed = "fixed"
    tiered = "tiered"
    hourly = "hourly"
    monthly = "monthly"


class ItemMediaType(str, enum.Enum):
    image = "image"
    document = "document"
    video = "video"


class CatalogItem(Base):
    __tablename__ = "catalog_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("actors.id"), index=True)
    type: Mapped[CatalogItemType] = mapped_column(Enum(CatalogItemType, name="catalog_item_type"))
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ItemStatus] = mapped_column(
        Enum(ItemStatus, name="item_status"), default=ItemStatus.draft
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    category: Mapped["Category"] = relationship()
    attributes: Mapped[list["ItemAttribute"]] = relationship(back_populates="item", cascade="all, delete-orphan")
    pricing: Mapped["ItemPricing | None"] = relationship(back_populates="item", uselist=False, cascade="all, delete-orphan")
    media: Mapped[list["ItemMedia"]] = relationship(back_populates="item", cascade="all, delete-orphan")
    stats: Mapped["ItemStats | None"] = relationship(back_populates="item", uselist=False, cascade="all, delete-orphan")


class ItemAttribute(Base):
    __tablename__ = "item_attributes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("catalog_items.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(255))
    value: Mapped[str] = mapped_column(String(500))
    value_type: Mapped[str] = mapped_column(String(50), default="text")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    item: Mapped["CatalogItem"] = relationship(back_populates="attributes")


class ItemPricing(Base):
    __tablename__ = "item_pricing"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("catalog_items.id", ondelete="CASCADE"), unique=True)
    pricing_type: Mapped[PricingType] = mapped_column(Enum(PricingType, name="pricing_type"))
    currency: Mapped[str] = mapped_column(String(10), default="RUB")
    fixed_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    hourly_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    monthly_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    tiers: Mapped[list] = mapped_column(JSONB, default=list)

    item: Mapped["CatalogItem"] = relationship(back_populates="pricing")


class ItemMedia(Base):
    __tablename__ = "item_media"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("catalog_items.id", ondelete="CASCADE"))
    file_name: Mapped[str] = mapped_column(String(255))
    file_url: Mapped[str] = mapped_column(String(500))
    media_type: Mapped[ItemMediaType] = mapped_column(Enum(ItemMediaType, name="item_media_type"))
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    item: Mapped["CatalogItem"] = relationship(back_populates="media")


class ItemStats(Base):
    __tablename__ = "item_stats"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("catalog_items.id", ondelete="CASCADE"), unique=True)
    views: Mapped[int] = mapped_column(Integer, default=0)
    leads: Mapped[int] = mapped_column(Integer, default=0)

    item: Mapped["CatalogItem"] = relationship(back_populates="stats")


class SupplierSubscriptionPlan(str, enum.Enum):
    none = "none"
    start = "start"
    pro = "pro"
    business = "business"


class SupplierSubscription(Base):
    __tablename__ = "supplier_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    plan: Mapped[SupplierSubscriptionPlan] = mapped_column(
        Enum(SupplierSubscriptionPlan, name="subscription_plan"),
        default=SupplierSubscriptionPlan.none,
    )
    active_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class OrderKind(str, enum.Enum):
    product = "product"
    service = "service"


class OrderStatus(str, enum.Enum):
    published = "published"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"
    disputed = "disputed"


class OrderOfferStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"
    withdrawn = "withdrawn"


class MarketplaceOrder(Base):
    __tablename__ = "marketplace_orders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    buyer_actor_id: Mapped[int] = mapped_column(ForeignKey("actors.id"), index=True)
    kind: Mapped[OrderKind] = mapped_column(Enum(OrderKind, name="order_kind"))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text, default="")
    category_id: Mapped[int | None] = mapped_column(ForeignKey("categories.id"), nullable=True)
    category_label: Mapped[str | None] = mapped_column(String(255), nullable=True)
    budget: Mapped[float] = mapped_column(Float, default=0)
    qty: Mapped[int] = mapped_column(Integer, default=1)
    needs_delivery: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[OrderStatus] = mapped_column(
        Enum(OrderStatus, name="order_status"), default=OrderStatus.published
    )
    accepted_offer_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    offers: Mapped[list["OrderOffer"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class OrderOffer(Base):
    __tablename__ = "order_offers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    order_id: Mapped[str] = mapped_column(ForeignKey("marketplace_orders.id", ondelete="CASCADE"), index=True)
    supplier_actor_id: Mapped[int] = mapped_column(ForeignKey("actors.id"), index=True)
    supplier_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    price: Mapped[float] = mapped_column(Float)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivery_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[OrderOfferStatus] = mapped_column(
        Enum(OrderOfferStatus, name="order_offer_status"), default=OrderOfferStatus.pending
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    order: Mapped["MarketplaceOrder"] = relationship(back_populates="offers")


class WithdrawalDestinationType(str, enum.Enum):
    bank = "bank"
    wallet = "wallet"


class WithdrawalStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class InvoiceStatus(str, enum.Enum):
    draft = "draft"
    issued = "issued"
    paid = "paid"
    overdue = "overdue"
    cancelled = "cancelled"


class WithdrawalDestination(Base):
    __tablename__ = "withdrawal_destinations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("actors.id"), index=True)
    type: Mapped[WithdrawalDestinationType] = mapped_column(
        Enum(WithdrawalDestinationType, name="withdrawal_destination_type")
    )
    label: Mapped[str] = mapped_column(String(255))
    details: Mapped[str] = mapped_column(Text)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)


class Withdrawal(Base):
    __tablename__ = "withdrawals"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("actors.id"), index=True)
    destination_id: Mapped[int] = mapped_column(ForeignKey("withdrawal_destinations.id"))
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(10), default="RUB")
    status: Mapped[WithdrawalStatus] = mapped_column(
        Enum(WithdrawalStatus, name="withdrawal_status"), default=WithdrawalStatus.pending
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SupplierInvoice(Base):
    __tablename__ = "supplier_invoices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[int] = mapped_column(ForeignKey("actors.id"), index=True)
    contract_id: Mapped[int | None] = mapped_column(ForeignKey("contracts.id"), nullable=True)
    number: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(255))
    amount: Mapped[float] = mapped_column(Float)
    currency: Mapped[str] = mapped_column(String(10), default="RUB")
    status: Mapped[InvoiceStatus] = mapped_column(
        Enum(InvoiceStatus, name="invoice_status"), default=InvoiceStatus.issued
    )
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
