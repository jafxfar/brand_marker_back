from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.exceptions import ConflictError, ForbiddenError, UnauthorizedError, ValidationError
from src.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from src.models import (
    Actor,
    ActorKind,
    ActorType,
    Company,
    CompanyRole,
    CompanyUser,
    RefreshTokenBlacklist,
    User,
    UserRole,
    UserStatus,
)
from src.modules.actors.service import ActorService, user_capabilities
from src.modules.auth.schemas import (
    ActivateRoleRequest,
    ActorSummary,
    CompanySummary,
    LoginRequest,
    MeResponse,
    RegisterRequest,
    TokenResponse,
    UserPublic,
    UserUpdateRequest,
)
from src.utils.audit import log_audit
from src.utils.redis_client import blacklist_refresh_token, is_refresh_token_blacklisted


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(self, data: RegisterRequest, ip: str | None = None) -> TokenResponse:
        existing = await self.db.execute(select(User).where(User.email == data.email.lower()))
        if existing.scalar_one_or_none():
            raise ConflictError("Email already registered")

        user = User(
            email=data.email.lower(),
            password_hash=hash_password(data.password),
            first_name=data.first_name,
            last_name=data.last_name,
            phone=data.phone,
            role=UserRole(data.role),
            status=UserStatus.active,
        )
        self.db.add(user)
        await self.db.flush()

        actor_svc = ActorService(self.db)
        await actor_svc.ensure_individual_actors_for_user(user)

        await log_audit(
            self.db,
            user_id=user.id,
            action="register",
            resource_type="user",
            resource_id=str(user.id),
            ip_address=ip,
        )
        return await self._issue_tokens(user)

    async def login(self, data: LoginRequest, ip: str | None = None) -> TokenResponse:
        result = await self.db.execute(select(User).where(User.email == data.email.lower()))
        user = result.scalar_one_or_none()
        if not user or not verify_password(data.password, user.password_hash):
            raise UnauthorizedError("Invalid email or password")
        if user.status == UserStatus.blocked:
            raise UnauthorizedError("Account is blocked")
        await log_audit(
            self.db,
            user_id=user.id,
            action="login",
            resource_type="user",
            resource_id=str(user.id),
            ip_address=ip,
        )
        return await self._issue_tokens(user)

    async def refresh(self, refresh_token: str) -> TokenResponse:
        try:
            payload = decode_token(refresh_token)
        except ValueError as exc:
            raise UnauthorizedError("Invalid refresh token") from exc
        if payload.get("type") != "refresh":
            raise UnauthorizedError("Invalid token type")
        import hashlib

        jti_hash = hashlib.sha256(payload["jti"].encode()).hexdigest()
        if await is_refresh_token_blacklisted(jti_hash):
            raise UnauthorizedError("Token revoked")
        user_id = int(payload["sub"])
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user:
            raise UnauthorizedError("User not found")
        return await self._issue_tokens(user)

    async def logout(self, refresh_token: str) -> None:
        try:
            payload = decode_token(refresh_token)
        except ValueError:
            return
        jti = payload.get("jti")
        if not jti:
            return
        import hashlib

        jti_hash = hashlib.sha256(jti.encode()).hexdigest()
        expires_at = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        self.db.add(RefreshTokenBlacklist(token_jti_hash=jti_hash, expires_at=expires_at))
        await blacklist_refresh_token(jti_hash, expires_at)

    def _actor_to_summary(self, actor: Actor, memberships: dict[int, CompanyUser]) -> ActorSummary:
        company_role = None
        verification_status = None
        if actor.kind == ActorKind.company and actor.company_id:
            membership = memberships.get(actor.company_id)
            if membership:
                company_role = membership.role.value
            if actor.company:
                verification_status = actor.company.verification_status.value
        return ActorSummary(
            id=actor.id,
            kind=actor.kind.value,
            side=actor.side.value,
            display_name=actor.display_name,
            trust_level=actor.trust_level.value,
            company_id=actor.company_id,
            verification_status=verification_status,
            company_role=company_role,
        )

    async def get_me(self, user: User, active_actor_id: int | None = None) -> MeResponse:
        actor_svc = ActorService(self.db)
        await actor_svc.ensure_individual_actors_for_user(user)

        result = await self.db.execute(
            select(CompanyUser)
            .where(CompanyUser.user_id == user.id)
            .options(selectinload(CompanyUser.company))
        )
        memberships = {m.company_id: m for m in result.scalars().all()}
        companies = [
            CompanySummary(
                id=m.company.id,
                title=m.company.title,
                actor_type=m.company.actor_type.value,
                verification_status=m.company.verification_status.value,
                role=m.role.value,
            )
            for m in memberships.values()
        ]

        actors = await actor_svc.list_for_user(user.id)
        actor_summaries = [self._actor_to_summary(a, memberships) for a in actors]

        valid_ids = {a.id for a in actors}
        if active_actor_id is not None and active_actor_id not in valid_ids:
            active_actor_id = None
        if active_actor_id is None and actor_summaries:
            individual = next((a for a in actor_summaries if a.kind == "individual"), None)
            active_actor_id = individual.id if individual else actor_summaries[0].id

        active_company_id = None
        if active_actor_id:
            active = next((a for a in actor_summaries if a.id == active_actor_id), None)
            if active and active.company_id:
                active_company_id = active.company_id

        return MeResponse(
            user=UserPublic.model_validate(user),
            actors=actor_summaries,
            active_actor_id=active_actor_id,
            capabilities=user_capabilities(user.role),
            companies=companies,
            active_company_id=active_company_id,
        )

    async def update_me(self, user: User, data: UserUpdateRequest) -> UserPublic:
        if data.first_name is not None:
            user.first_name = data.first_name
        if data.last_name is not None:
            user.last_name = data.last_name
        if data.phone is not None:
            user.phone = data.phone
        user.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
        return UserPublic.model_validate(user)

    async def switch_actor(self, user: User, actor_id: int) -> MeResponse:
        actor_svc = ActorService(self.db)
        actor = await actor_svc.get_by_id(actor_id)
        if not actor or not await actor_svc.user_owns_actor(user.id, actor):
            raise ValidationError("Actor not linked to user")
        return await self.get_me(user, active_actor_id=actor_id)

    async def switch_company(self, user: User, company_id: int) -> MeResponse:
        result = await self.db.execute(
            select(CompanyUser).where(
                CompanyUser.user_id == user.id, CompanyUser.company_id == company_id
            )
        )
        if not result.scalar_one_or_none():
            raise ValidationError("Company not linked to user")
        company = await self.db.get(Company, company_id)
        if not company:
            raise ValidationError("Company not found")
        actor_svc = ActorService(self.db)
        actor = await actor_svc.get_company_actor(company_id, company.actor_type)
        if not actor:
            raise ValidationError("Company actor not found")
        return await self.get_me(user, active_actor_id=actor.id)

    async def activate_role(self, user: User, data: ActivateRoleRequest) -> MeResponse:
        side = ActorType(data.side)
        if side == ActorType.buyer and user.role == UserRole.supplier:
            user.role = UserRole.both
        elif side == ActorType.supplier and user.role == UserRole.buyer:
            user.role = UserRole.both
        elif side == ActorType.buyer and user.role not in (UserRole.buyer, UserRole.both):
            user.role = UserRole.buyer
        elif side == ActorType.supplier and user.role not in (UserRole.supplier, UserRole.both):
            user.role = UserRole.supplier
        user.updated_at = datetime.now(timezone.utc)
        await self.db.flush()

        actor_svc = ActorService(self.db)
        actor = await actor_svc.ensure_individual_actor(user, side)
        return await self.get_me(user, active_actor_id=actor.id)

    async def _issue_tokens(self, user: User) -> TokenResponse:
        access = create_access_token(str(user.id), {"role": user.role.value})
        refresh, _ = create_refresh_token(str(user.id))
        return TokenResponse(access_token=access, refresh_token=refresh)
