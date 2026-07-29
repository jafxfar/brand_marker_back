from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from src.models import (
    Currency,
    NotificationType,
    PaymentType,
    Proposal,
    ProposalStatus,
    Rfq,
    RfqStatus,
)
from src.modules.contracts.service import ContractService
from src.modules.notifications.service import NotificationService
from src.modules.proposals.schemas import ProposalCreate, ProposalUpdate
from src.shared.serializers import proposal_to_schema


class ProposalService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _load(self, proposal_id: int) -> Proposal:
        result = await self.db.execute(
            select(Proposal)
            .where(Proposal.id == proposal_id)
            .options(selectinload(Proposal.attachment), selectinload(Proposal.rfq))
        )
        p = result.scalar_one_or_none()
        if not p:
            raise NotFoundError("Proposal not found")
        return p

    async def list_for_rfq(self, rfq_id: str, buyer_actor_id: int) -> list:
        from src.modules.rfqs.service import RfqService

        rfq = await RfqService(self.db)._load(rfq_id)
        if rfq.actor_id != buyer_actor_id:
            raise ForbiddenError("Access denied")
        result = await self.db.execute(
            select(Proposal)
            .where(Proposal.rfq_id == rfq_id)
            .options(selectinload(Proposal.attachment))
            .order_by(Proposal.created_at.desc())
        )
        proposals = result.scalars().all()
        for p in proposals:
            if p.status == ProposalStatus.submitted:
                p.status = ProposalStatus.viewed
        await self.db.flush()
        return [proposal_to_schema(p) for p in proposals]

    async def list_for_supplier(self, supplier_id: int) -> list:
        result = await self.db.execute(
            select(Proposal)
            .where(Proposal.supplier_actor_id == supplier_id)
            .options(selectinload(Proposal.attachment))
            .order_by(Proposal.created_at.desc())
        )
        return [proposal_to_schema(p) for p in result.scalars().all()]

    async def submit(self, rfq_id: str, supplier_id: int, data: ProposalCreate):
        from src.modules.rfqs.service import RfqService

        rfq = await RfqService(self.db)._load(rfq_id)
        if rfq.status not in (RfqStatus.published, RfqStatus.receiving_proposals):
            raise ConflictError("RFQ is not accepting proposals")
        if rfq.visibility.value == "invited_only":
            if not any(i.supplier_actor_id == supplier_id for i in rfq.invited_suppliers):
                raise ForbiddenError("Not invited to this RFQ")
        existing = await self.db.execute(
            select(Proposal).where(
                Proposal.rfq_id == rfq_id, Proposal.supplier_actor_id == supplier_id
            )
        )
        if existing.scalar_one_or_none():
            raise ConflictError("Proposal already submitted")
        proposal = Proposal(
            rfq_id=rfq_id,
            supplier_actor_id=supplier_id,
            price=data.price,
            currency=Currency(data.currency),
            delivery_time=data.delivery_time,
            message=data.message,
            status=ProposalStatus.submitted,
        )
        self.db.add(proposal)
        await self.db.flush()
        notif = NotificationService(self.db)
        await notif.notify_actor_members(
            rfq.actor_id,
            NotificationType.proposal,
            "Новый отклик",
            f"Поставщик отправил предложение на RFQ «{rfq.title}»",
            f"/customer/rfqs/{rfq.id}/proposals",
        )
        return proposal_to_schema(await self._load(proposal.id))

    async def update_proposal(self, proposal_id: int, supplier_id: int, data: ProposalUpdate):
        proposal = await self._load(proposal_id)
        if proposal.supplier_actor_id != supplier_id:
            raise ForbiddenError("Access denied")
        if proposal.status != ProposalStatus.submitted:
            raise ConflictError("Proposal cannot be edited")
        if data.price is not None:
            proposal.price = data.price
        if data.currency is not None:
            proposal.currency = Currency(data.currency)
        if data.delivery_time is not None:
            proposal.delivery_time = data.delivery_time
        if data.message is not None:
            proposal.message = data.message
        await self.db.flush()
        return proposal_to_schema(proposal)

    async def withdraw(self, proposal_id: int, supplier_id: int):
        proposal = await self._load(proposal_id)
        if proposal.supplier_actor_id != supplier_id:
            raise ForbiddenError("Access denied")
        proposal.status = ProposalStatus.withdrawn
        await self.db.flush()
        return proposal_to_schema(proposal)

    async def shortlist(self, proposal_id: int, buyer_actor_id: int):
        proposal = await self._load(proposal_id)
        if proposal.rfq.actor_id != buyer_actor_id:
            raise ForbiddenError("Access denied")
        proposal.status = ProposalStatus.shortlisted
        await self.db.flush()
        return proposal_to_schema(proposal)

    async def reject(self, proposal_id: int, buyer_actor_id: int):
        proposal = await self._load(proposal_id)
        if proposal.rfq.actor_id != buyer_actor_id:
            raise ForbiddenError("Access denied")
        proposal.status = ProposalStatus.rejected
        await self.db.flush()
        return proposal_to_schema(proposal)

    async def accept(
        self,
        proposal_id: int,
        buyer_actor_id: int,
        payment_type: PaymentType | None = None,
        milestones: list[dict] | None = None,
    ):
        proposal = await self._load(proposal_id)
        rfq = proposal.rfq
        if rfq.actor_id != buyer_actor_id:
            raise ForbiddenError("Access denied")
        if proposal.status in (ProposalStatus.accepted, ProposalStatus.rejected, ProposalStatus.withdrawn):
            raise ConflictError("Proposal already finalized")
        proposal.status = ProposalStatus.accepted
        rfq.status = RfqStatus.supplier_selected
        result = await self.db.execute(
            select(Proposal).where(Proposal.rfq_id == rfq.id, Proposal.id != proposal_id)
        )
        for other in result.scalars().all():
            if other.status not in (ProposalStatus.rejected, ProposalStatus.withdrawn):
                other.status = ProposalStatus.rejected
        await self.db.flush()
        contract_svc = ContractService(self.db)
        contract = await contract_svc.create_from_proposal(
            proposal,
            buyer_actor_id,
            payment_type=payment_type,
            milestones=milestones,
        )
        rfq.status = RfqStatus.contract_created
        await self.db.flush()
        notif = NotificationService(self.db)
        await notif.notify_supplier_on_accept(proposal, contract.id)
        return {"proposal": proposal_to_schema(proposal), "contract_id": contract.id}
