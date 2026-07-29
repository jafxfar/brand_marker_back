from dataclasses import dataclass
from typing import Annotated

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.exceptions import ForbiddenError, UnauthorizedError
from src.core.security import decode_token
from src.db.session import get_db
from src.models import Actor, ActorKind, ActorType, Company, CompanyRole, CompanyUser, User, UserStatus
from src.modules.actors.service import ActorService

security = HTTPBearer(auto_error=False)

FINANCE_ROLES = {CompanyRole.director, CompanyRole.admin, CompanyRole.accountant}
FULL_COMPANY_ROLES = {CompanyRole.director, CompanyRole.admin}
RFQ_ROLES = FULL_COMPANY_ROLES | {CompanyRole.moderator}


@dataclass
class AuthContext:
    user: User
    actor: Actor | None
    company: Company | None
    company_role: CompanyRole | None


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    if not credentials:
        raise UnauthorizedError("Missing authentication token")
    try:
        payload = decode_token(credentials.credentials)
    except ValueError as exc:
        raise UnauthorizedError("Invalid or expired token") from exc
    if payload.get("type") != "access":
        raise UnauthorizedError("Invalid token type")
    user_id = int(payload["sub"])
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise UnauthorizedError("User not found")
    if user.status == UserStatus.blocked:
        raise ForbiddenError("Account is blocked")
    return user


async def _resolve_actor_context(
    user: User,
    db: AsyncSession,
    x_actor_id: int | None,
    x_company_id: int | None,
    side: ActorType | None,
    *,
    strict: bool,
) -> AuthContext:
    actor_svc = ActorService(db)
    actor = await actor_svc.resolve_actor_id(
        user.id,
        x_actor_id,
        x_company_id,
        side,
        strict=strict,
    )
    company = None
    company_role = None
    if actor and actor.kind == ActorKind.company and actor.company_id:
        result = await db.execute(
            select(CompanyUser)
            .where(
                CompanyUser.user_id == user.id,
                CompanyUser.company_id == actor.company_id,
            )
            .options(selectinload(CompanyUser.company))
        )
        membership = result.scalar_one_or_none()
        if membership:
            company = membership.company
            company_role = membership.role
    return AuthContext(user=user, actor=actor, company=company, company_role=company_role)


async def get_auth_context(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
    x_actor_id: Annotated[int | None, Header(alias="X-Actor-Id")] = None,
    x_company_id: Annotated[int | None, Header(alias="X-Company-Id")] = None,
) -> AuthContext:
    return await _resolve_actor_context(
        user, db, x_actor_id, x_company_id, side=None, strict=False
    )


async def require_actor(
    ctx: Annotated[AuthContext, Depends(get_auth_context)],
) -> AuthContext:
    if not ctx.actor:
        raise ForbiddenError("X-Actor-Id header required", code="actor_required")
    return ctx


def require_company_roles(*roles: CompanyRole):
    async def _check(ctx: Annotated[AuthContext, Depends(require_actor)]) -> AuthContext:
        if ctx.actor and ctx.actor.kind == ActorKind.individual:
            return ctx
        if not ctx.company_role or ctx.company_role not in roles:
            raise ForbiddenError("Insufficient company permissions")
        return ctx

    return _check


async def get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
