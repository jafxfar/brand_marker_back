from datetime import datetime, timezone

from sqlalchemy import String, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.exceptions import ForbiddenError, NotFoundError
from src.models import (
    CatalogItem,
    Company,
    Contract,
    ContractStatus,
    PaymentMilestone,
    PaymentMilestoneStatus,
    Rfq,
    RfqStatus,
    SupplierInvoice,
    InvoiceStatus,
    User,
    UserRole,
    UserStatus,
    VerificationStatus,
)
from src.modules.auth.schemas import UserPublic


class AdminService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_users(
        self,
        page: int = 1,
        page_size: int = 20,
        status: UserStatus | None = None,
        query: str | None = None,
    ) -> dict:
        search_filters = []
        normalized_query = query.strip() if query else ""
        if normalized_query:
            search_pattern = f"%{normalized_query}%"
            search_conditions = [
                User.email.ilike(search_pattern),
                User.first_name.ilike(search_pattern),
                User.last_name.ilike(search_pattern),
                (User.first_name + " " + User.last_name).ilike(search_pattern),
                User.phone.ilike(search_pattern),
                cast(User.id, String).ilike(search_pattern),
            ]
            if normalized_query.isdigit():
                search_conditions.append(User.id == int(normalized_query))
            search_filters.append(or_(*search_conditions))

        filters = list(search_filters)
        if status:
            filters.append(User.status == status)

        total_result = await self.db.execute(
            select(func.count()).select_from(User).where(*filters)
        )
        total = int(total_result.scalar_one())

        counts_result = await self.db.execute(
            select(User.status, func.count())
            .where(*search_filters)
            .group_by(User.status)
        )
        counts = {user_status.value: count for user_status, count in counts_result.all()}

        users_result = await self.db.execute(
            select(User)
            .where(*filters)
            .order_by(User.created_at.desc(), User.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        items = [UserPublic.model_validate(user) for user in users_result.scalars().all()]

        return {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": max(1, (total + page_size - 1) // page_size),
            "status_counts": {
                "all": sum(counts.values()),
                "active": counts.get(UserStatus.active.value, 0),
                "blocked": counts.get(UserStatus.blocked.value, 0),
                "pending": counts.get(UserStatus.pending.value, 0),
            },
        }

    async def get_dashboard(self) -> dict:
        async def count(model, *filters) -> int:
            statement = select(func.count()).select_from(model)
            if filters:
                statement = statement.where(*filters)
            result = await self.db.execute(statement)
            return int(result.scalar_one())

        active_rfq_statuses = {
            RfqStatus.published,
            RfqStatus.receiving_proposals,
            RfqStatus.supplier_selected,
            RfqStatus.contract_created,
            RfqStatus.in_progress,
        }
        active_contract_statuses = {
            ContractStatus.pending_payment,
            ContractStatus.active,
            ContractStatus.delivered,
        }
        escrow_statuses = {
            PaymentMilestoneStatus.funded,
            PaymentMilestoneStatus.in_progress,
            PaymentMilestoneStatus.submitted,
            PaymentMilestoneStatus.approved,
            PaymentMilestoneStatus.disputed,
        }
        month_start = datetime.now(timezone.utc).replace(
            day=1,
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )

        escrow_result = await self.db.execute(
            select(func.coalesce(func.sum(PaymentMilestone.amount), 0.0)).where(
                PaymentMilestone.status.in_(escrow_statuses)
            )
        )
        revenue_result = await self.db.execute(
            select(func.coalesce(func.sum(SupplierInvoice.amount), 0.0)).where(
                SupplierInvoice.status == InvoiceStatus.paid,
                SupplierInvoice.paid_at >= month_start,
            )
        )

        metrics = {
            "total_users": await count(User),
            "total_companies": await count(Company),
            "catalog_items": await count(CatalogItem),
            "active_rfqs": await count(Rfq, Rfq.status.in_(active_rfq_statuses)),
            "active_contracts": await count(
                Contract,
                Contract.status.in_(active_contract_statuses),
            ),
            "escrow_balance": float(escrow_result.scalar_one()),
            "open_disputes": await count(
                Contract,
                Contract.status == ContractStatus.disputed,
            ),
            "monthly_revenue": float(revenue_result.scalar_one()),
            "pending_verifications": await count(
                Company,
                Company.verification_status == VerificationStatus.pending,
            ),
        }

        recent_users = (
            await self.db.execute(select(User).order_by(User.created_at.desc()).limit(5))
        ).scalars().all()
        recent_contracts = (
            await self.db.execute(
                select(Contract).order_by(Contract.created_at.desc()).limit(5)
            )
        ).scalars().all()
        recent_payments = (
            await self.db.execute(
                select(SupplierInvoice)
                .where(SupplierInvoice.status == InvoiceStatus.paid)
                .order_by(SupplierInvoice.paid_at.desc())
                .limit(5)
            )
        ).scalars().all()
        recent_disputes = (
            await self.db.execute(
                select(Contract)
                .where(Contract.status == ContractStatus.disputed)
                .order_by(Contract.created_at.desc())
                .limit(5)
            )
        ).scalars().all()

        activity = [
            {
                "id": f"user-{user.id}",
                "type": "registration",
                "title": f"{user.first_name} {user.last_name}".strip() or user.email,
                "description": user.email,
                "happened_at": user.created_at,
            }
            for user in recent_users
        ]
        activity.extend(
            {
                "id": f"contract-{contract.id}",
                "type": "contract",
                "title": contract.title,
                "description": f"Контракт #{contract.id}",
                "happened_at": contract.created_at,
            }
            for contract in recent_contracts
        )
        activity.extend(
            {
                "id": f"payment-{invoice.id}",
                "type": "payment",
                "title": invoice.title,
                "description": f"{invoice.amount:g} {invoice.currency}",
                "happened_at": invoice.paid_at or invoice.issued_at,
            }
            for invoice in recent_payments
        )
        activity.extend(
            {
                "id": f"dispute-{contract.id}",
                "type": "dispute",
                "title": contract.title,
                "description": f"Спор по контракту #{contract.id}",
                "happened_at": contract.created_at,
            }
            for contract in recent_disputes
        )
        activity.sort(key=lambda item: item["happened_at"], reverse=True)

        return {"metrics": metrics, "recent_activity": activity[:12]}

    async def update_user_status(
        self,
        user_id: int,
        status: str,
        current_user: User,
    ) -> UserPublic:
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundError("User not found")
        if user.id == current_user.id:
            raise ForbiddenError("You cannot change your own account status")

        role_rank = {
            UserRole.moderator: 1,
            UserRole.admin: 2,
            UserRole.superadmin: 3,
        }
        current_rank = role_rank.get(current_user.role, 0)
        target_rank = role_rank.get(user.role, 0)
        if target_rank and target_rank >= current_rank:
            raise ForbiddenError("You cannot change this staff account status")

        user.status = UserStatus(status)
        await self.db.flush()
        return UserPublic.model_validate(user)

    async def list_pending_verification(self) -> list[dict]:
        result = await self.db.execute(
            select(Company).where(Company.verification_status == VerificationStatus.pending)
        )
        return [
            {
                "id": c.id,
                "title": c.title,
                "actor_type": c.actor_type.value,
                "owner_id": c.owner_id,
                "verification_status": c.verification_status.value,
            }
            for c in result.scalars().all()
        ]

    async def verify_company(self, company_id: int, approved: bool) -> dict:
        result = await self.db.execute(select(Company).where(Company.id == company_id))
        company = result.scalar_one_or_none()
        if not company:
            raise NotFoundError("Company not found")
        company.verification_status = (
            VerificationStatus.verified if approved else VerificationStatus.rejected
        )
        await self.db.flush()
        return {"id": company.id, "verification_status": company.verification_status.value}

    async def list_disputes(self) -> list[dict]:
        result = await self.db.execute(
            select(Contract)
            .where(Contract.status == ContractStatus.disputed)
            .options(selectinload(Contract.rfq))
        )
        return [
            {
                "contract_id": c.id,
                "rfq_id": c.rfq_id,
                "buyer_actor_id": c.buyer_actor_id,
                "supplier_actor_id": c.supplier_actor_id,
                "title": c.title,
                "status": c.status.value,
            }
            for c in result.scalars().all()
        ]

    async def resolve_dispute(self, contract_id: int, resolution: str) -> dict:
        result = await self.db.execute(select(Contract).where(Contract.id == contract_id))
        contract = result.scalar_one_or_none()
        if not contract:
            raise NotFoundError("Contract not found")
        if contract.status != ContractStatus.disputed:
            raise NotFoundError("Contract is not in dispute")
        contract.status = ContractStatus.completed if resolution == "buyer" else ContractStatus.cancelled
        await self.db.flush()
        return {"contract_id": contract.id, "status": contract.status.value, "resolution": resolution}
