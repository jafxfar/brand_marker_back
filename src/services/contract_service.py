from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from src.models import (
    Contract,
    ContractFile,
    ContractStatus,
    Conversation,
    Currency,
    Message,
    PaymentMilestone,
    PaymentMilestoneStatus,
    PaymentMilestoneTrigger,
    PaymentPlan,
    PaymentType,
    Proposal,
    RfqStatus,
    WorkSubmission,
    WorkSubmissionStatus,
    WorkSubmissionType,
)
from src.schemas.contract import DisputeRequest, MessageCreate, WorkSubmissionCreate
from src.services.serializers import contract_to_schema


def _default_milestones(contract: Contract, payment_type: PaymentType) -> list[dict]:
    amount = contract.agreed_amount
    if payment_type == PaymentType.full_prepayment:
        return [
            {
                "title": "Полная предоплата",
                "percentage": 100,
                "amount": amount,
                "trigger": PaymentMilestoneTrigger.contract_signed.value,
                "status": PaymentMilestoneStatus.awaiting_payment,
            }
        ]
    if payment_type == PaymentType.full_postpayment:
        return [
            {
                "title": "Оплата после приёмки",
                "percentage": 100,
                "amount": amount,
                "trigger": PaymentMilestoneTrigger.delivery_accepted.value,
                "status": PaymentMilestoneStatus.pending,
            }
        ]
    if payment_type == PaymentType.split_payment:
        return [
            {
                "title": "Предоплата 50%",
                "percentage": 50,
                "amount": round(amount * 0.5, 2),
                "trigger": PaymentMilestoneTrigger.contract_signed.value,
                "status": PaymentMilestoneStatus.awaiting_payment,
            },
            {
                "title": "Оплата 50% после приёмки",
                "percentage": 50,
                "amount": round(amount * 0.5, 2),
                "trigger": PaymentMilestoneTrigger.delivery_accepted.value,
                "status": PaymentMilestoneStatus.pending,
            },
        ]
    return [
        {
            "title": "Этап 1 — подписание",
            "percentage": 30,
            "amount": round(amount * 0.3, 2),
            "trigger": PaymentMilestoneTrigger.contract_signed.value,
            "status": PaymentMilestoneStatus.awaiting_payment,
        },
        {
            "title": "Этап 2 — промежуточная сдача",
            "percentage": 40,
            "amount": round(amount * 0.4, 2),
            "trigger": PaymentMilestoneTrigger.delivery_accepted.value,
            "status": PaymentMilestoneStatus.pending,
        },
        {
            "title": "Этап 3 — финальная приёмка",
            "percentage": 30,
            "amount": round(amount * 0.3, 2),
            "trigger": PaymentMilestoneTrigger.delivery_accepted.value,
            "status": PaymentMilestoneStatus.pending,
        },
    ]


class ContractService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _load(self, contract_id: int) -> Contract:
        result = await self.db.execute(
            select(Contract)
            .where(Contract.id == contract_id)
            .options(
                selectinload(Contract.payment_plan).selectinload(PaymentPlan.milestones),
                selectinload(Contract.conversation)
                .selectinload(Conversation.messages)
                .selectinload(Message.sender),
                selectinload(Contract.files),
                selectinload(Contract.submissions),
                selectinload(Contract.rfq),
            )
        )
        c = result.scalar_one_or_none()
        if not c:
            raise NotFoundError("Contract not found")
        return c

    async def create_from_proposal(self, proposal: Proposal, buyer_actor_id: int) -> Contract:
        rfq = proposal.rfq
        payment_type = PaymentType.milestone
        if hasattr(rfq, "budget_type"):
            payment_type = PaymentType.split_payment
        contract = Contract(
            rfq_id=rfq.id,
            proposal_id=proposal.id,
            buyer_actor_id=buyer_actor_id,
            supplier_actor_id=proposal.supplier_actor_id,
            title=rfq.title,
            description=rfq.description,
            agreed_amount=proposal.price,
            currency=proposal.currency,
            start_date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            due_date=rfq.deadline,
            payment_type=payment_type,
            status=ContractStatus.pending_payment,
        )
        self.db.add(contract)
        await self.db.flush()
        plan = PaymentPlan(contract_id=contract.id, payment_type=payment_type)
        self.db.add(plan)
        await self.db.flush()
        for m in _default_milestones(contract, payment_type):
            self.db.add(
                PaymentMilestone(
                    payment_plan_id=plan.id,
                    contract_id=contract.id,
                    title=m["title"],
                    percentage=m["percentage"],
                    amount=m["amount"],
                    trigger=m["trigger"],
                    status=m["status"],
                )
            )
        conv = Conversation(contract_id=contract.id)
        self.db.add(conv)
        await self.db.flush()
        return contract

    async def list_for_actor(self, actor_id: int, actor_type: str) -> list:
        if actor_type == "buyer":
            stmt = select(Contract).where(Contract.buyer_actor_id == actor_id)
        else:
            stmt = select(Contract).where(Contract.supplier_actor_id == actor_id)
        result = await self.db.execute(
            stmt.options(
                selectinload(Contract.payment_plan).selectinload(PaymentPlan.milestones),
                selectinload(Contract.conversation)
                .selectinload(Conversation.messages)
                .selectinload(Message.sender),
                selectinload(Contract.files),
                selectinload(Contract.submissions),
            ).order_by(Contract.created_at.desc())
        )
        return [contract_to_schema(c) for c in result.scalars().all()]

    async def get(self, contract_id: int, actor_id: int) -> dict:
        contract = await self._load(contract_id)
        if contract.buyer_actor_id != actor_id and contract.supplier_actor_id != actor_id:
            raise ForbiddenError("Access denied")
        return contract_to_schema(contract)

    async def add_message(self, contract_id: int, user_id: int, actor_id: int, data: MessageCreate):
        contract = await self._load(contract_id)
        if contract.buyer_actor_id != actor_id and contract.supplier_actor_id != actor_id:
            raise ForbiddenError("Access denied")
        if not contract.conversation:
            contract.conversation = Conversation(contract_id=contract_id)
            await self.db.flush()
        msg = Message(
            conversation_id=contract.conversation.id,
            sender_id=user_id,
            text=data.text,
        )
        self.db.add(msg)
        await self.db.flush()
        return contract_to_schema(await self._load(contract_id))

    async def add_file(
        self, contract_id: int, user_id: int, actor_id: int, file_name: str, file_url: str, file_type: str
    ):
        contract = await self._load(contract_id)
        if contract.buyer_actor_id != actor_id and contract.supplier_actor_id != actor_id:
            raise ForbiddenError("Access denied")
        self.db.add(
            ContractFile(
                contract_id=contract_id,
                file_name=file_name,
                file_url=file_url,
                file_type=file_type,
                uploaded_by=user_id,
            )
        )
        await self.db.flush()
        return contract_to_schema(await self._load(contract_id))

    async def submit_work(
        self, contract_id: int, supplier_id: int, data: WorkSubmissionCreate
    ):
        contract = await self._load(contract_id)
        if contract.supplier_actor_id != supplier_id:
            raise ForbiddenError("Access denied")
        if contract.status not in (ContractStatus.active, ContractStatus.pending_payment):
            raise ConflictError("Contract not active")
        assets = [
            {
                "kind": a.kind,
                "name": a.name,
                "url": a.url,
                "file_type": a.file_type,
            }
            for a in getattr(data, "assets", []) or []
        ]
        file_names = data.file_names or [a["name"] for a in assets]
        sub = WorkSubmission(
            contract_id=contract_id,
            type=WorkSubmissionType(data.type),
            note=data.note,
            status=WorkSubmissionStatus.pending,
            file_names=file_names,
            assets=assets,
        )
        self.db.add(sub)
        contract.status = ContractStatus.delivered
        await self.db.flush()
        return contract_to_schema(await self._load(contract_id))

    async def approve_submission(self, contract_id: int, submission_id: int, buyer_id: int):
        contract = await self._load(contract_id)
        if contract.buyer_actor_id != buyer_id:
            raise ForbiddenError("Access denied")
        sub = next((s for s in contract.submissions if s.id == submission_id), None)
        if not sub:
            raise NotFoundError("Submission not found")
        sub.status = WorkSubmissionStatus.accepted
        contract.status = ContractStatus.completed
        if contract.rfq:
            contract.rfq.status = RfqStatus.completed
        if contract.payment_plan:
            for m in contract.payment_plan.milestones:
                if m.status == PaymentMilestoneStatus.funded:
                    m.status = PaymentMilestoneStatus.released
                elif m.status == PaymentMilestoneStatus.pending:
                    m.status = PaymentMilestoneStatus.awaiting_payment
        await self.db.flush()
        return contract_to_schema(await self._load(contract_id))

    async def reject_submission(self, contract_id: int, submission_id: int, buyer_id: int):
        contract = await self._load(contract_id)
        if contract.buyer_actor_id != buyer_id:
            raise ForbiddenError("Access denied")
        sub = next((s for s in contract.submissions if s.id == submission_id), None)
        if not sub:
            raise NotFoundError("Submission not found")
        sub.status = WorkSubmissionStatus.rejected
        contract.status = ContractStatus.active
        await self.db.flush()
        return contract_to_schema(await self._load(contract_id))

    async def open_dispute(self, contract_id: int, actor_id: int, data: DisputeRequest):
        contract = await self._load(contract_id)
        if contract.buyer_actor_id != actor_id and contract.supplier_actor_id != actor_id:
            raise ForbiddenError("Access denied")
        contract.status = ContractStatus.disputed
        if contract.rfq:
            contract.rfq.status = RfqStatus.disputed
        await self.db.flush()
        return contract_to_schema(await self._load(contract_id))
