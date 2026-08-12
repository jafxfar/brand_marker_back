from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from src.models import (
    Contract,
    ContractStatus,
    PaymentMilestone,
    PaymentMilestoneStatus,
    PaymentPlan,
)
from src.modules.payments.schemas import (
    PaymentHistoryItem,
    PendingPaymentItem,
    SupplierBalanceSchema,
)


class PaymentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_milestones(self, contract_id: int, actor_id: int):
        result = await self.db.execute(
            select(Contract)
            .where(Contract.id == contract_id)
            .options(selectinload(Contract.payment_plan).selectinload(PaymentPlan.milestones))
        )
        contract = result.scalar_one_or_none()
        if not contract:
            raise NotFoundError("Contract not found")
        if contract.buyer_actor_id != actor_id and contract.supplier_actor_id != actor_id:
            raise ForbiddenError("Access denied")
        if not contract.payment_plan:
            return None
        from src.modules.contracts.schemas import PaymentPlanSchema

        return PaymentPlanSchema.model_validate(
            {
                "id": contract.payment_plan.id,
                "contract_id": contract.payment_plan.contract_id,
                "payment_type": contract.payment_plan.payment_type.value,
                "milestones": [
                    {
                        "id": m.id,
                        "contract_id": m.contract_id,
                        "title": m.title,
                        "percentage": m.percentage,
                        "amount": m.amount,
                        "trigger": m.trigger,
                        "status": m.status.value,
                    }
                    for m in contract.payment_plan.milestones
                ],
            }
        )

    async def fund_milestone(self, milestone_id: int, buyer_id: int, idempotency_key: str | None = None):
        result = await self.db.execute(
            select(PaymentMilestone).where(PaymentMilestone.id == milestone_id)
        )
        milestone = result.scalar_one_or_none()
        if not milestone:
            raise NotFoundError("Milestone not found")
        result = await self.db.execute(select(Contract).where(Contract.id == milestone.contract_id))
        contract = result.scalar_one_or_none()
        if not contract or contract.buyer_actor_id != buyer_id:
            raise ForbiddenError("Access denied")
        if milestone.status not in (
            PaymentMilestoneStatus.pending,
            PaymentMilestoneStatus.awaiting_payment,
        ):
            raise ConflictError("Milestone cannot be funded")
        milestone.status = PaymentMilestoneStatus.funded
        if contract.status == ContractStatus.pending_payment:
            contract.status = ContractStatus.active
        await self.db.flush()
        return milestone

    async def approve_milestone(self, milestone_id: int, buyer_id: int):
        result = await self.db.execute(
            select(PaymentMilestone).where(PaymentMilestone.id == milestone_id)
        )
        milestone = result.scalar_one_or_none()
        if not milestone:
            raise NotFoundError("Milestone not found")
        result = await self.db.execute(select(Contract).where(Contract.id == milestone.contract_id))
        contract = result.scalar_one_or_none()
        if not contract or contract.buyer_actor_id != buyer_id:
            raise ForbiddenError("Access denied")
        if milestone.status != PaymentMilestoneStatus.funded:
            raise ConflictError("Milestone must be funded first")
        milestone.status = PaymentMilestoneStatus.released
        await self.db.flush()
        if contract.supplier_actor_id:
            from src.modules.supplier_finance.service import SupplierFinanceService

            await SupplierFinanceService(self.db).create_invoice_for_milestone(
                contract.supplier_actor_id,
                contract.id,
                milestone.id,
                milestone.title,
                milestone.amount,
                contract.currency.value,
            )
        return milestone

    async def payment_history(self, buyer_id: int) -> list[PaymentHistoryItem]:
        result = await self.db.execute(
            select(Contract)
            .where(Contract.buyer_actor_id == buyer_id)
            .options(selectinload(Contract.payment_plan).selectinload(PaymentPlan.milestones))
        )
        items: list[PaymentHistoryItem] = []
        for contract in result.scalars().all():
            if not contract.payment_plan:
                continue
            for m in contract.payment_plan.milestones:
                if m.status in (
                    PaymentMilestoneStatus.funded,
                    PaymentMilestoneStatus.released,
                    PaymentMilestoneStatus.refunded,
                ):
                    items.append(
                        PaymentHistoryItem(
                            contract_id=contract.id,
                            milestone_id=m.id,
                            title=m.title,
                            amount=m.amount,
                            currency=contract.currency.value,
                            status=m.status.value,
                            event="funded" if m.status == PaymentMilestoneStatus.funded else m.status.value,
                            created_at=contract.created_at,
                        )
                    )
        return items

    async def pending_payments(self, buyer_id: int) -> list[PendingPaymentItem]:
        result = await self.db.execute(
            select(Contract)
            .where(Contract.buyer_actor_id == buyer_id)
            .options(selectinload(Contract.payment_plan).selectinload(PaymentPlan.milestones))
        )
        items: list[PendingPaymentItem] = []
        for contract in result.scalars().all():
            if not contract.payment_plan:
                continue
            for m in contract.payment_plan.milestones:
                if m.status in (
                    PaymentMilestoneStatus.pending,
                    PaymentMilestoneStatus.awaiting_payment,
                ):
                    items.append(
                        PendingPaymentItem(
                            contract_id=contract.id,
                            milestone_id=m.id,
                            title=m.title,
                            amount=m.amount,
                            currency=contract.currency.value,
                            status=m.status.value,
                        )
                    )
        return items

    async def _supplier_contracts(self, supplier_actor_id: int) -> list[Contract]:
        result = await self.db.execute(
            select(Contract)
            .where(Contract.supplier_actor_id == supplier_actor_id)
            .options(selectinload(Contract.payment_plan).selectinload(PaymentPlan.milestones))
        )
        return list(result.scalars().all())

    async def supplier_payment_history(
        self, supplier_actor_id: int
    ) -> list[PaymentHistoryItem]:
        items: list[PaymentHistoryItem] = []
        for contract in await self._supplier_contracts(supplier_actor_id):
            if not contract.payment_plan:
                continue
            for m in contract.payment_plan.milestones:
                if m.status in (
                    PaymentMilestoneStatus.funded,
                    PaymentMilestoneStatus.released,
                    PaymentMilestoneStatus.refunded,
                ):
                    items.append(
                        PaymentHistoryItem(
                            contract_id=contract.id,
                            milestone_id=m.id,
                            title=m.title,
                            amount=m.amount,
                            currency=contract.currency.value,
                            status=m.status.value,
                            event=m.status.value,
                            created_at=contract.created_at,
                        )
                    )
        return items

    async def supplier_pending_payouts(
        self, supplier_actor_id: int
    ) -> list[PendingPaymentItem]:
        items: list[PendingPaymentItem] = []
        for contract in await self._supplier_contracts(supplier_actor_id):
            if not contract.payment_plan:
                continue
            for m in contract.payment_plan.milestones:
                if m.status in (
                    PaymentMilestoneStatus.funded,
                    PaymentMilestoneStatus.released,
                ):
                    items.append(
                        PendingPaymentItem(
                            contract_id=contract.id,
                            milestone_id=m.id,
                            title=m.title,
                            amount=m.amount,
                            currency=contract.currency.value,
                            status=m.status.value,
                        )
                    )
        return items

    async def supplier_balance(self, supplier_actor_id: int) -> SupplierBalanceSchema:
        available = 0.0
        pending = 0.0
        escrow_locked = 0.0
        currency = "TJS"
        for contract in await self._supplier_contracts(supplier_actor_id):
            if not contract.payment_plan:
                continue
            currency = contract.currency.value
            for m in contract.payment_plan.milestones:
                if m.status == PaymentMilestoneStatus.released:
                    available += m.amount
                elif m.status == PaymentMilestoneStatus.funded:
                    pending += m.amount
                    escrow_locked += m.amount

        from src.models import Withdrawal, WithdrawalStatus

        result = await self.db.execute(
            select(Withdrawal).where(
                Withdrawal.actor_id == supplier_actor_id,
                Withdrawal.status.in_(
                    [WithdrawalStatus.pending, WithdrawalStatus.processing, WithdrawalStatus.completed]
                ),
            )
        )
        withdrawn = sum(w.amount for w in result.scalars().all())
        available = max(0.0, available - withdrawn)

        return SupplierBalanceSchema(
            available=available,
            pending=pending,
            escrow_locked=escrow_locked,
            currency=currency,
        )

    async def mock_confirm_payment(self, milestone_id: int, buyer_id: int) -> dict:
        milestone = await self.fund_milestone(milestone_id, buyer_id)
        return {
            "status": "confirmed",
            "milestone_id": milestone.id,
            "milestone_status": milestone.status.value,
        }
