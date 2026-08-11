from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import SupplierSubscription, SupplierSubscriptionPlan, User
from src.modules.subscription.schemas import SubscriptionResponse

COMPANY_LIMITS: dict[str, int | None] = {
    "none": 1,
    "start": 2,
    "pro": 5,
    "business": None,
}

CATALOG_LIMITS: dict[str, int | None] = {
    "none": 10,
    "start": 10,
    "pro": 50,
    "business": None,
}

THIRTY_DAYS = timedelta(days=30)


class SubscriptionService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_or_create(self, user_id: int) -> SupplierSubscription:
        result = await self.db.execute(
            select(SupplierSubscription).where(SupplierSubscription.user_id == user_id)
        )
        sub = result.scalar_one_or_none()
        if not sub:
            sub = SupplierSubscription(user_id=user_id, plan=SupplierSubscriptionPlan.none)
            self.db.add(sub)
            await self.db.flush()
        return sub

    def _is_active(self, sub: SupplierSubscription) -> bool:
        if sub.plan == SupplierSubscriptionPlan.none:
            return False
        return sub.active_until is not None and sub.active_until > datetime.now(timezone.utc)

    async def get_subscription(self, user_id: int) -> SubscriptionResponse:
        sub = await self._get_or_create(user_id)
        return SubscriptionResponse(
            plan=sub.plan.value,
            active_until=sub.active_until,
            is_active=self._is_active(sub),
        )

    async def activate(self, user_id: int, plan: str) -> SubscriptionResponse:
        sub = await self._get_or_create(user_id)
        sub.plan = SupplierSubscriptionPlan(plan)
        sub.active_until = datetime.now(timezone.utc) + THIRTY_DAYS
        await self.db.flush()
        from src.modules.finance.ledger import (
            SUBSCRIPTION_PLAN_AMOUNTS,
            FinanceLedgerService,
        )
        from src.models import (
            PlatformPaymentGateway,
            PlatformPaymentStatus,
            PlatformPaymentType,
        )

        amount = SUBSCRIPTION_PLAN_AMOUNTS.get(plan, 0.0)
        if amount > 0:
            await FinanceLedgerService(self.db).record(
                payment_type=PlatformPaymentType.subscription,
                amount=amount,
                currency="RUB",
                title=f"Подписка {plan}",
                description=f"Активация тарифа {plan} на 30 дней",
                status=PlatformPaymentStatus.paid,
                gateway=PlatformPaymentGateway.mock,
                subscription_user_id=user_id,
                metadata={"plan": plan},
            )
        return await self.get_subscription(user_id)

    async def cancel(self, user_id: int) -> SubscriptionResponse:
        sub = await self._get_or_create(user_id)
        sub.plan = SupplierSubscriptionPlan.none
        sub.active_until = None
        await self.db.flush()
        return await self.get_subscription(user_id)

    async def get_effective_plan(self, user_id: int) -> str:
        sub = await self._get_or_create(user_id)
        if self._is_active(sub):
            return sub.plan.value
        return "none"

    async def check_company_limit(self, user: User) -> None:
        from src.core.exceptions import ConflictError
        from src.models import Company

        plan = await self.get_effective_plan(user.id)
        limit = COMPANY_LIMITS.get(plan, 1)
        if limit is None:
            return
        result = await self.db.execute(
            select(Company).where(Company.owner_id == user.id)
        )
        count = len(list(result.scalars().all()))
        if count >= limit:
            raise ConflictError(f"Company limit reached for plan {plan}")

    async def check_catalog_limit(self, user_id: int, actor_id: int) -> None:
        from src.core.exceptions import ConflictError
        from src.models import CatalogItem, ItemStatus

        plan = await self.get_effective_plan(user_id)
        limit = CATALOG_LIMITS.get(plan, 10)
        if limit is None:
            return
        result = await self.db.execute(
            select(CatalogItem).where(
                CatalogItem.actor_id == actor_id,
                CatalogItem.status == ItemStatus.active,
            )
        )
        count = len(list(result.scalars().all()))
        if count >= limit:
            raise ConflictError(f"Active catalog item limit reached for plan {plan}")
