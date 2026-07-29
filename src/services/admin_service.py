from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.exceptions import NotFoundError
from src.models import Company, Contract, ContractStatus, User, UserStatus, VerificationStatus
from src.schemas.auth import UserPublic


class AdminService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_users(self, skip: int = 0, limit: int = 50) -> list[UserPublic]:
        result = await self.db.execute(select(User).offset(skip).limit(limit))
        return [UserPublic.model_validate(u) for u in result.scalars().all()]

    async def update_user_status(self, user_id: int, status: str) -> UserPublic:
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise NotFoundError("User not found")
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
