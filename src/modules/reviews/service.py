from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from src.models import Actor, Company, CompanyStats, Contract, ContractStatus, Review
from src.modules.reviews.schemas import ReviewCreate, ReviewResponse


class ReviewService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, reviewer_actor_id: int, data: ReviewCreate) -> ReviewResponse:
        result = await self.db.execute(select(Contract).where(Contract.id == data.contract_id))
        contract = result.scalar_one_or_none()
        if not contract:
            raise NotFoundError("Contract not found")
        if contract.buyer_actor_id != reviewer_actor_id:
            raise ForbiddenError("Only buyer can leave review")
        if contract.status != ContractStatus.completed:
            raise ConflictError("Contract must be completed")
        existing = await self.db.execute(
            select(Review).where(
                Review.contract_id == data.contract_id,
                Review.reviewer_actor_id == reviewer_actor_id,
            )
        )
        if existing.scalar_one_or_none():
            raise ConflictError("Review already exists")
        review = Review(
            contract_id=data.contract_id,
            reviewer_actor_id=reviewer_actor_id,
            target_actor_id=data.target_actor_id,
            rating=data.rating,
            comment=data.comment,
        )
        self.db.add(review)
        await self._update_actor_rating(data.target_actor_id)
        await self.db.flush()
        return ReviewResponse.model_validate(review)

    async def list_for_company(self, company_id: int) -> list[ReviewResponse]:
        actor_result = await self.db.execute(
            select(Actor.id).where(Actor.company_id == company_id)
        )
        actor_ids = [row[0] for row in actor_result.all()]
        if not actor_ids:
            return []
        result = await self.db.execute(
            select(Review)
            .where(Review.target_actor_id.in_(actor_ids))
            .order_by(Review.created_at.desc())
        )
        return [ReviewResponse.model_validate(r) for r in result.scalars().all()]

    async def list_for_reviewer(self, reviewer_actor_id: int) -> list[ReviewResponse]:
        result = await self.db.execute(
            select(Review)
            .where(Review.reviewer_actor_id == reviewer_actor_id)
            .order_by(Review.created_at.desc())
        )
        return [ReviewResponse.model_validate(r) for r in result.scalars().all()]

    async def _update_actor_rating(self, target_actor_id: int) -> None:
        result = await self.db.execute(
            select(func.avg(Review.rating)).where(Review.target_actor_id == target_actor_id)
        )
        avg = result.scalar() or 0.0
        actor_result = await self.db.execute(
            select(Actor)
            .where(Actor.id == target_actor_id)
            .options(selectinload(Actor.company))
        )
        actor = actor_result.scalar_one_or_none()
        if not actor or not actor.company_id:
            return
        company_result = await self.db.execute(
            select(Company).where(Company.id == actor.company_id)
        )
        company = company_result.scalar_one_or_none()
        if company:
            company.rating = round(float(avg), 2)
            if company.stats:
                company.stats.average_rating = company.rating
