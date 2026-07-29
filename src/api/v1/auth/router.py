from typing import Annotated

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import get_settings
from src.core.deps import AuthContext, get_auth_context, get_client_ip, get_current_user
from src.core.exceptions import ForbiddenError
from src.db.session import get_db
from src.models import User
from src.modules.auth.schemas import (
    ActivateRoleRequest,
    LoginRequest,
    LogoutRequest,
    MeResponse,
    RefreshRequest,
    RegisterRequest,
    SwitchActorRequest,
    SwitchCompanyRequest,
    TokenResponse,
    UserPublic,
    UserUpdateRequest,
)
from src.modules.auth.service import AuthService
from src.utils.redis_client import check_rate_limit

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()


@router.post("/register", response_model=TokenResponse)
async def register(
    data: RegisterRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    ip = await get_client_ip(request)
    return await AuthService(db).register(data, ip)


@router.post("/login", response_model=TokenResponse)
async def login(
    data: LoginRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    ip = await get_client_ip(request)
    allowed = await check_rate_limit(
        f"login:{ip}", settings.rate_limit_login_per_minute, 60
    )
    if not allowed:
        raise ForbiddenError("Too many login attempts. Try again later.")
    return await AuthService(db).login(data, ip)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(data: RefreshRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    return await AuthService(db).refresh(data.refresh_token)


@router.post("/logout", status_code=204)
async def logout(data: LogoutRequest, db: Annotated[AsyncSession, Depends(get_db)]):
    await AuthService(db).logout(data.refresh_token)


@router.get("/me", response_model=MeResponse)
async def me(
    user: Annotated[User, Depends(get_current_user)],
    ctx: Annotated[AuthContext, Depends(get_auth_context)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    active = ctx.actor.id if ctx.actor else None
    return await AuthService(db).get_me(user, active)


@router.patch("/me", response_model=UserPublic)
async def update_me(
    data: UserUpdateRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await AuthService(db).update_me(user, data)


@router.post("/switch-actor", response_model=MeResponse)
async def switch_actor(
    data: SwitchActorRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await AuthService(db).switch_actor(user, data.actor_id)


@router.post("/switch-company", response_model=MeResponse)
async def switch_company(
    data: SwitchCompanyRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await AuthService(db).switch_company(user, data.company_id)


@router.post("/activate-role", response_model=MeResponse)
async def activate_role(
    data: ActivateRoleRequest,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await AuthService(db).activate_role(user, data)
