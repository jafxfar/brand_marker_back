from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.deps import require_admin
from src.db.session import get_db
from src.models import User, UserStatus
from src.modules.admin.service import AdminService
from src.modules.auth.schemas import UserPublic

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


class UserStatusUpdate(BaseModel):
    status: Literal["pending", "active", "blocked"]


class AdminUserStatusCounts(BaseModel):
    all: int
    active: int
    blocked: int
    pending: int


class AdminUsersResponse(BaseModel):
    items: list[UserPublic]
    total: int
    page: int
    page_size: int
    pages: int
    status_counts: AdminUserStatusCounts


class VerifyCompanyRequest(BaseModel):
    approved: bool = True


class ResolveDisputeRequest(BaseModel):
    resolution: str


class AdminDashboardMetrics(BaseModel):
    total_users: int
    total_companies: int
    catalog_items: int
    active_rfqs: int
    active_contracts: int
    escrow_balance: float
    open_disputes: int
    monthly_revenue: float
    pending_verifications: int


class AdminActivityItem(BaseModel):
    id: str
    type: Literal["registration", "contract", "payment", "dispute"]
    title: str
    description: str
    happened_at: datetime


class AdminDashboardResponse(BaseModel):
    metrics: AdminDashboardMetrics
    recent_activity: list[AdminActivityItem]


@router.get("/dashboard", response_model=AdminDashboardResponse)
async def admin_dashboard(
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await AdminService(db).get_dashboard()


@router.get("/users", response_model=AdminUsersResponse)
async def admin_list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    status: Literal["active", "blocked", "pending"] | None = None,
    query: Annotated[str | None, Query(max_length=255)] = None,
):
    return await AdminService(db).list_users(
        page=page,
        page_size=page_size,
        status=UserStatus(status) if status else None,
        query=query,
    )


@router.patch("/users/{user_id}/status", response_model=UserPublic)
async def admin_update_user_status(
    user_id: int,
    data: UserStatusUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(require_admin)],
):
    return await AdminService(db).update_user_status(
        user_id,
        data.status,
        current_user,
    )


@router.get("/companies/pending-verification")
async def admin_pending_verification(
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await AdminService(db).list_pending_verification()


@router.post("/companies/{company_id}/verify")
async def admin_verify_company(
    company_id: int,
    data: VerifyCompanyRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await AdminService(db).verify_company(company_id, data.approved)


@router.get("/disputes")
async def admin_list_disputes(
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await AdminService(db).list_disputes()


@router.post("/disputes/{contract_id}/resolve")
async def admin_resolve_dispute(
    contract_id: int,
    data: ResolveDisputeRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await AdminService(db).resolve_dispute(contract_id, data.resolution)
