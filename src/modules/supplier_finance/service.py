from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from src.models import (
    InvoiceStatus,
    SupplierInvoice,
    Withdrawal,
    WithdrawalDestination,
    WithdrawalDestinationType,
    WithdrawalStatus,
)
from src.modules.payments.service import PaymentService
from src.modules.supplier_finance.schemas import (
    InvoiceSchema,
    WithdrawalCreate,
    WithdrawalDestinationCreate,
    WithdrawalDestinationSchema,
    WithdrawalSchema,
)


class SupplierFinanceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_destinations(self, actor_id: int) -> list[WithdrawalDestinationSchema]:
        result = await self.db.execute(
            select(WithdrawalDestination).where(WithdrawalDestination.actor_id == actor_id)
        )
        return [
            WithdrawalDestinationSchema(
                id=d.id,
                actor_id=d.actor_id,
                type=d.type.value,
                label=d.label,
                details=d.details,
                is_default=d.is_default,
            )
            for d in result.scalars().all()
        ]

    async def create_destination(
        self, actor_id: int, data: WithdrawalDestinationCreate
    ) -> WithdrawalDestinationSchema:
        dest = WithdrawalDestination(
            actor_id=actor_id,
            type=WithdrawalDestinationType(data.type),
            label=data.label,
            details=data.details,
            is_default=data.is_default,
        )
        self.db.add(dest)
        await self.db.flush()
        return WithdrawalDestinationSchema(
            id=dest.id,
            actor_id=dest.actor_id,
            type=dest.type.value,
            label=dest.label,
            details=dest.details,
            is_default=dest.is_default,
        )

    async def list_withdrawals(self, actor_id: int) -> list[WithdrawalSchema]:
        result = await self.db.execute(
            select(Withdrawal)
            .where(Withdrawal.actor_id == actor_id)
            .order_by(Withdrawal.created_at.desc())
        )
        return [
            WithdrawalSchema(
                id=w.id,
                actor_id=w.actor_id,
                destination_id=w.destination_id,
                amount=w.amount,
                currency=w.currency,
                status=w.status.value,
                created_at=w.created_at,
                completed_at=w.completed_at,
            )
            for w in result.scalars().all()
        ]

    async def request_withdrawal(
        self, actor_id: int, data: WithdrawalCreate
    ) -> WithdrawalSchema:
        balance = await PaymentService(self.db).supplier_balance(actor_id)
        pending_withdrawals = await self.db.execute(
            select(Withdrawal).where(
                Withdrawal.actor_id == actor_id,
                Withdrawal.status.in_([WithdrawalStatus.pending, WithdrawalStatus.processing]),
            )
        )
        pending_amount = sum(w.amount for w in pending_withdrawals.scalars().all())
        available = balance.available - pending_amount
        if data.amount > available:
            raise ConflictError("Insufficient available balance")

        dest_result = await self.db.execute(
            select(WithdrawalDestination).where(
                WithdrawalDestination.id == data.destination_id,
                WithdrawalDestination.actor_id == actor_id,
            )
        )
        if not dest_result.scalar_one_or_none():
            raise NotFoundError("Destination not found")

        withdrawal = Withdrawal(
            actor_id=actor_id,
            destination_id=data.destination_id,
            amount=data.amount,
            currency=balance.currency,
            status=WithdrawalStatus.pending,
        )
        self.db.add(withdrawal)
        await self.db.flush()
        return WithdrawalSchema(
            id=withdrawal.id,
            actor_id=withdrawal.actor_id,
            destination_id=withdrawal.destination_id,
            amount=withdrawal.amount,
            currency=withdrawal.currency,
            status=withdrawal.status.value,
            created_at=withdrawal.created_at,
            completed_at=withdrawal.completed_at,
        )

    async def list_invoices(self, actor_id: int) -> list[InvoiceSchema]:
        result = await self.db.execute(
            select(SupplierInvoice)
            .where(SupplierInvoice.actor_id == actor_id)
            .order_by(SupplierInvoice.issued_at.desc())
        )
        return [
            InvoiceSchema(
                id=i.id,
                actor_id=i.actor_id,
                contract_id=i.contract_id,
                number=i.number,
                title=i.title,
                amount=i.amount,
                currency=i.currency,
                status=i.status.value,
                issued_at=i.issued_at,
                due_at=i.due_at,
                paid_at=i.paid_at,
            )
            for i in result.scalars().all()
        ]

    async def create_invoice_for_milestone(
        self,
        actor_id: int,
        contract_id: int,
        milestone_id: int,
        title: str,
        amount: float,
        currency: str,
    ) -> SupplierInvoice:
        invoice = SupplierInvoice(
            actor_id=actor_id,
            contract_id=contract_id,
            number=f"INV-{contract_id}-{milestone_id}",
            title=title,
            amount=amount,
            currency=currency,
            status=InvoiceStatus.paid,
            paid_at=datetime.now(timezone.utc),
        )
        self.db.add(invoice)
        await self.db.flush()
        return invoice
