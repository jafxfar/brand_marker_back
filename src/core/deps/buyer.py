from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.deps.auth import FINANCE_ROLES, RFQ_ROLES, get_current_user
from src.core.exceptions import ForbiddenError
from src.db.session import get_db
from src.models import Actor, ActorKind, ActorType, Company, CompanyRole, CompanyUser, User, UserRole
from src.modules.actors.service import ActorService


@dataclass
class BuyerContext:
    user: User
    actor: Actor
    company: Company | None
    company_role: CompanyRole | None


async def require_buyer_ctx(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_actor_id: Annotated[int | None, Header(alias="X-Actor-Id")] = None,
    x_company_id: Annotated[int | None, Header(alias="X-Company-Id")] = None,
) -> BuyerContext:
    actor_svc = ActorService(db)
    actor = await actor_svc.resolve_actor_id(
        user.id, x_actor_id, x_company_id, ActorType.buyer, strict=True
    )
    if not actor:
        raise ForbiddenError("Buyer actor required", code="actor_required")
    if actor.side != ActorType.buyer:
        raise ForbiddenError("Buyer actor required")
    if user.role not in (UserRole.buyer, UserRole.both):
        raise ForbiddenError("Buyer platform role required")

    company = None
    company_role = None
    if actor.company_id:
        result = await db.execute(
            select(CompanyUser)
            .where(CompanyUser.user_id == user.id, CompanyUser.company_id == actor.company_id)
            .options(selectinload(CompanyUser.company))
        )
        membership = result.scalar_one_or_none()
        if not membership:
            raise ForbiddenError("Not a member of this company")
        company = membership.company
        company_role = membership.role

    return BuyerContext(
        user=user,
        actor=actor,
        company=company,
        company_role=company_role or CompanyRole.director,
    )


def require_buyer_company_roles(*roles: CompanyRole):
    async def _check(
        ctx: Annotated[BuyerContext, Depends(require_buyer_ctx)],
    ) -> BuyerContext:
        if ctx.actor.kind == ActorKind.individual:
            return ctx
        if not ctx.company_role or ctx.company_role not in roles:
            raise ForbiddenError("Insufficient company permissions")
        return ctx

    return _check
