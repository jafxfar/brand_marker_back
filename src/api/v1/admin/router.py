from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.deps import require_admin
from src.db.session import get_db
from src.models import User
from src.modules.admin.service import AdminService
from src.modules.auth.schemas import UserPublic

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


class UserStatusUpdate(BaseModel):
    status: str


class VerifyCompanyRequest(BaseModel):
    approved: bool = True


class ResolveDisputeRequest(BaseModel):
    resolution: str


@router.get("/users", response_model=list[UserPublic])
async def admin_list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await AdminService(db).list_users()


@router.patch("/users/{user_id}/status", response_model=UserPublic)
async def admin_update_user_status(
    user_id: int,
    data: UserStatusUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await AdminService(db).update_user_status(user_id, data.status)


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
