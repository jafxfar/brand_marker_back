from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.deps.auth import get_current_user
from src.core.exceptions import ForbiddenError
from src.db.session import get_db
from src.models import Actor, ActorType, Company, CompanyRole, CompanyUser, User, UserRole
from src.modules.actors.service import ActorService


@dataclass
class SupplierContext:
    user: User
    actor: Actor
    company: Company | None
    company_role: CompanyRole | None


async def require_supplier_ctx(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_actor_id: Annotated[int | None, Header(alias="X-Actor-Id")] = None,
    x_company_id: Annotated[int | None, Header(alias="X-Company-Id")] = None,
) -> SupplierContext:
    actor_svc = ActorService(db)
    actor = await actor_svc.resolve_actor_id(
        user.id, x_actor_id, x_company_id, ActorType.supplier, strict=True
    )
    if not actor:
        raise ForbiddenError("Supplier actor required", code="actor_required")
    if actor.side != ActorType.supplier:
        raise ForbiddenError("Supplier actor required")
    if user.role not in (UserRole.supplier, UserRole.both):
        raise ForbiddenError("Supplier platform role required")

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

    return SupplierContext(
        user=user,
        actor=actor,
        company=company,
        company_role=company_role or CompanyRole.director,
    )
