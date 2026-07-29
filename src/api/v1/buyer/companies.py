from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.deps import BuyerContext, require_buyer_ctx
from src.db.session import get_db
from src.modules.companies.schemas import (
    AddTeamMemberRequest,
    CertificateCreateRequest,
    CompanyUpdateRequest,
    CompanyWizardInput,
    CompanyWithRelations,
)
from src.modules.companies.service import CompanyService

router = APIRouter(prefix="/companies", tags=["buyer-companies"])


@router.post("/", response_model=CompanyWithRelations)
async def create_company(
    data: CompanyWizardInput,
    ctx: Annotated[BuyerContext, Depends(require_buyer_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await CompanyService(db).create_from_wizard(ctx.user, data)


@router.get("/me", response_model=list[CompanyWithRelations])
async def my_companies(
    ctx: Annotated[BuyerContext, Depends(require_buyer_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await CompanyService(db).get_my_companies(ctx.user.id)


@router.patch("/{company_id}", response_model=CompanyWithRelations)
async def update_company(
    company_id: int,
    data: CompanyUpdateRequest,
    ctx: Annotated[BuyerContext, Depends(require_buyer_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await CompanyService(db).update_company(company_id, ctx.user.id, data)


@router.post("/{company_id}/certificates")
async def add_certificate(
    company_id: int,
    data: CertificateCreateRequest,
    ctx: Annotated[BuyerContext, Depends(require_buyer_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    cert = await CompanyService(db).add_certificate(company_id, ctx.user.id, data)
    return {"id": cert.id}


@router.post("/{company_id}/team")
async def add_team_member(
    company_id: int,
    data: AddTeamMemberRequest,
    ctx: Annotated[BuyerContext, Depends(require_buyer_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    member = await CompanyService(db).add_team_member(company_id, ctx.user.id, data)
    return {"id": member.id}


@router.delete("/{company_id}/team/{target_user_id}", status_code=204)
async def remove_team_member(
    company_id: int,
    target_user_id: int,
    ctx: Annotated[BuyerContext, Depends(require_buyer_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await CompanyService(db).remove_team_member(company_id, ctx.user.id, target_user_id)
