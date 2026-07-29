from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models import (
    Actor,
    ActorKind,
    ActorType,
    Company,
    CompanyUser,
    TrustLevel,
    User,
    UserRole,
    VerificationStatus,
)


def individual_display_name(user: User) -> str:
    return f"{user.first_name} {user.last_name}".strip() or user.email


def trust_level_for_company(company: Company) -> TrustLevel:
    if company.verification_status == VerificationStatus.verified:
        return TrustLevel.verified
    return TrustLevel.standard


def user_capabilities(role: UserRole) -> dict[str, bool]:
    return {
        "buyer": role in (UserRole.buyer, UserRole.both),
        "supplier": role in (UserRole.supplier, UserRole.both),
    }


def sides_for_role(role: UserRole) -> list[ActorType]:
    if role == UserRole.both:
        return [ActorType.buyer, ActorType.supplier]
    if role == UserRole.supplier:
        return [ActorType.supplier]
    return [ActorType.buyer]


class ActorService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_id(self, actor_id: int) -> Actor | None:
        result = await self.db.execute(
            select(Actor)
            .where(Actor.id == actor_id, Actor.is_active.is_(True))
            .options(selectinload(Actor.company))
        )
        return result.scalar_one_or_none()

    async def list_for_user(self, user_id: int) -> list[Actor]:
        company_ids_subq = select(CompanyUser.company_id).where(CompanyUser.user_id == user_id)
        result = await self.db.execute(
            select(Actor)
            .where(
                Actor.is_active.is_(True),
                or_(
                    Actor.user_id == user_id,
                    Actor.company_id.in_(company_ids_subq),
                ),
            )
            .options(selectinload(Actor.company))
            .order_by(Actor.kind, Actor.side, Actor.id)
        )
        return list(result.scalars().all())

    async def user_owns_actor(self, user_id: int, actor: Actor) -> bool:
        if actor.kind == ActorKind.individual:
            return actor.user_id == user_id
        if actor.company_id is None:
            return False
        result = await self.db.execute(
            select(CompanyUser).where(
                CompanyUser.user_id == user_id,
                CompanyUser.company_id == actor.company_id,
            )
        )
        return result.scalar_one_or_none() is not None

    async def get_individual_actor(self, user_id: int, side: ActorType) -> Actor | None:
        result = await self.db.execute(
            select(Actor).where(
                Actor.kind == ActorKind.individual,
                Actor.user_id == user_id,
                Actor.side == side,
                Actor.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def get_company_actor(self, company_id: int, side: ActorType) -> Actor | None:
        result = await self.db.execute(
            select(Actor).where(
                Actor.kind == ActorKind.company,
                Actor.company_id == company_id,
                Actor.side == side,
                Actor.is_active.is_(True),
            )
        )
        return result.scalar_one_or_none()

    async def ensure_individual_actor(self, user: User, side: ActorType) -> Actor:
        existing = await self.get_individual_actor(user.id, side)
        if existing:
            return existing
        actor = Actor(
            kind=ActorKind.individual,
            side=side,
            user_id=user.id,
            company_id=None,
            display_name=individual_display_name(user),
            trust_level=TrustLevel.basic,
            is_active=True,
        )
        self.db.add(actor)
        await self.db.flush()
        return actor

    async def ensure_individual_actors_for_user(self, user: User) -> list[Actor]:
        actors: list[Actor] = []
        for side in sides_for_role(user.role):
            actors.append(await self.ensure_individual_actor(user, side))
        return actors

    async def ensure_company_actor(self, company: Company, side: ActorType) -> Actor:
        existing = await self.get_company_actor(company.id, side)
        if existing:
            existing.display_name = company.title
            existing.trust_level = trust_level_for_company(company)
            existing.is_active = True
            existing.updated_at = datetime.now(timezone.utc)
            await self.db.flush()
            return existing
        actor = Actor(
            kind=ActorKind.company,
            side=side,
            user_id=None,
            company_id=company.id,
            display_name=company.title,
            trust_level=trust_level_for_company(company),
            is_active=True,
        )
        self.db.add(actor)
        await self.db.flush()
        return actor

    async def sync_company_actors(
        self, company: Company, actor_types: list[ActorType]
    ) -> list[Actor]:
        actors: list[Actor] = []
        for side in actor_types:
            actors.append(await self.ensure_company_actor(company, side))
        for side in ActorType:
            if side not in actor_types:
                actor = await self.get_company_actor(company.id, side)
                if actor:
                    actor.is_active = False
                    actor.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        return actors

    async def resolve_actor_id(
        self,
        user_id: int,
        x_actor_id: int | None,
        x_company_id: int | None,
        side: ActorType | None = None,
        *,
        strict: bool = False,
    ) -> Actor | None:
        actor_svc = self
        if x_actor_id is not None:
            actor = await actor_svc.get_by_id(x_actor_id)
            if not actor:
                return None
            if not await actor_svc.user_owns_actor(user_id, actor):
                return None
            if side and actor.side != side:
                return None
            return actor

        if x_company_id is not None and side is not None:
            result = await self.db.execute(
                select(CompanyUser).where(
                    CompanyUser.user_id == user_id,
                    CompanyUser.company_id == x_company_id,
                )
            )
            if not result.scalar_one_or_none():
                return None
            return await actor_svc.get_company_actor(x_company_id, side)

        if strict:
            return None

        actors = await actor_svc.list_for_user(user_id)
        if side:
            actors = [a for a in actors if a.side == side]
        return actors[0] if actors else None
