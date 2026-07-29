from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.exceptions import ConflictError, UnauthorizedError, ValidationError
from src.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from src.models import (
    ActorType,
    Company,
    CompanyRole,
    CompanyUser,
    RefreshTokenBlacklist,
    User,
    UserRole,
    UserStatus,
)
from src.schemas.auth import (
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
        jti = payload.get("jti")
        if not jti:
            raise UnauthorizedError("Invalid refresh token")
        import hashlib

        jti_hash = hashlib.sha256(jti.encode()).hexdigest()
        if await is_refresh_token_blacklisted(jti_hash):
            raise UnauthorizedError("Token has been revoked")
        result = await self.db.execute(
            select(RefreshTokenBlacklist).where(RefreshTokenBlacklist.token_jti_hash == jti_hash)
        )
        if result.scalar_one_or_none():
            raise UnauthorizedError("Token has been revoked")
        user_id = int(payload["sub"])
        result = await self.db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if not user or user.status == UserStatus.blocked:
            raise UnauthorizedError("User not found or blocked")
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

    async def get_me(self, user: User, active_company_id: int | None = None) -> MeResponse:
        result = await self.db.execute(
            select(CompanyUser)
            .where(CompanyUser.user_id == user.id)
            .options(selectinload(CompanyUser.company))
        )
        memberships = result.scalars().all()
        companies = [
            CompanySummary(
                id=m.company.id,
                title=m.company.title,
                actor_type=m.company.actor_type.value,
                verification_status=m.company.verification_status.value,
                role=m.role.value,
            )
            for m in memberships
        ]
        if active_company_id is None and companies:
            active_company_id = companies[0].id
        return MeResponse(
            user=UserPublic.model_validate(user),
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

    async def switch_company(self, user: User, company_id: int) -> MeResponse:
        result = await self.db.execute(
            select(CompanyUser).where(
                CompanyUser.user_id == user.id, CompanyUser.company_id == company_id
            )
        )
        if not result.scalar_one_or_none():
            raise ValidationError("Company not linked to user")
        return await self.get_me(user, active_company_id=company_id)

    async def _issue_tokens(self, user: User) -> TokenResponse:
        access = create_access_token(str(user.id), {"role": user.role.value})
        refresh, _ = create_refresh_token(str(user.id))
        return TokenResponse(access_token=access, refresh_token=refresh)
