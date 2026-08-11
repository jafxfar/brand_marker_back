from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.models import (
    PlatformPayment,
    PlatformPaymentGateway,
    PlatformPaymentStatus,
    PlatformPaymentType,
)


SUBSCRIPTION_PLAN_AMOUNTS: dict[str, float] = {
    "start": 1990.0,
    "pro": 4990.0,
    "business": 14990.0,
}


class FinanceLedgerService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def record(
        self,
        *,
        payment_type: PlatformPaymentType,
        amount: float,
        title: str,
        status: PlatformPaymentStatus = PlatformPaymentStatus.pending,
        gateway: PlatformPaymentGateway = PlatformPaymentGateway.manual,
        currency: str = "RUB",
        commission: float = 0.0,
        description: str | None = None,
        actor_id: int | None = None,
        invoice_id: int | None = None,
        withdrawal_id: int | None = None,
        contract_id: int | None = None,
        subscription_user_id: int | None = None,
        external_id: str | None = None,
        metadata: dict | None = None,
        paid_at: datetime | None = None,
    ) -> PlatformPayment:
        now = datetime.now(timezone.utc)
        payment = PlatformPayment(
            type=payment_type,
            status=status,
            gateway=gateway,
            amount=amount,
            commission=commission,
            currency=currency,
            title=title,
            description=description,
            actor_id=actor_id,
            invoice_id=invoice_id,
            withdrawal_id=withdrawal_id,
            contract_id=contract_id,
            subscription_user_id=subscription_user_id,
            external_id=external_id,
            metadata_json=metadata,
            paid_at=paid_at or (now if status == PlatformPaymentStatus.paid else None),
            failed_at=now if status == PlatformPaymentStatus.failed else None,
            refunded_at=now if status == PlatformPaymentStatus.refunded else None,
        )
        self.db.add(payment)
        await self.db.flush()
        return payment
