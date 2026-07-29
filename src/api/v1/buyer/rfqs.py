from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.deps import BuyerContext, require_buyer_ctx, require_buyer_company_roles
from src.db.session import get_db
from src.models import CompanyRole
from src.modules.rfqs.schemas import InviteSuppliersRequest, ProductRfqCreate, ServiceRfqCreate
from src.modules.rfqs.service import RfqService
from src.utils.storage import storage_service

router = APIRouter(prefix="/rfqs", tags=["buyer-rfqs"])


@router.get("/")
async def list_rfqs(
    ctx: Annotated[BuyerContext, Depends(require_buyer_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
    tab: str | None = Query(None),
):
    return await RfqService(db).list_for_buyer(ctx.actor.id, tab)


@router.post("/")
async def create_rfq(
    data: ProductRfqCreate | ServiceRfqCreate,
    ctx: Annotated[
        BuyerContext,
        Depends(require_buyer_company_roles(CompanyRole.director, CompanyRole.admin, CompanyRole.moderator)),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    created_by = f"{ctx.user.first_name} {ctx.user.last_name}".strip()
    return await RfqService(db).create(ctx.actor.id, created_by, data)


@router.get("/{rfq_id}")
async def get_rfq(
    rfq_id: str,
    ctx: Annotated[BuyerContext, Depends(require_buyer_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await RfqService(db).get(rfq_id, actor_id=ctx.actor.id)


@router.patch("/{rfq_id}")
async def update_rfq(
    rfq_id: str,
    data: dict,
    ctx: Annotated[
        BuyerContext,
        Depends(require_buyer_company_roles(CompanyRole.director, CompanyRole.admin, CompanyRole.moderator)),
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await RfqService(db).update(rfq_id, ctx.actor.id, data)


@router.post("/{rfq_id}/publish")
async def publish_rfq(
    rfq_id: str,
    ctx: Annotated[BuyerContext, Depends(require_buyer_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await RfqService(db).publish(rfq_id, ctx.actor.id)


@router.post("/{rfq_id}/close")
async def close_rfq(
    rfq_id: str,
    ctx: Annotated[BuyerContext, Depends(require_buyer_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await RfqService(db).close(rfq_id, ctx.actor.id)


@router.post("/{rfq_id}/attachments")
async def upload_attachment(
    rfq_id: str,
    ctx: Annotated[BuyerContext, Depends(require_buyer_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...),
):
    _, url = await storage_service.upload(file, f"rfqs/{rfq_id}")
    return await RfqService(db).add_attachment(
        rfq_id, ctx.actor.id, file.filename or "file", url, file.content_type or "application/octet-stream"
    )


@router.delete("/{rfq_id}/attachments/{attachment_id}")
async def delete_attachment(
    rfq_id: str,
    attachment_id: str,
    ctx: Annotated[BuyerContext, Depends(require_buyer_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await RfqService(db).remove_attachment(rfq_id, ctx.actor.id, attachment_id)


@router.post("/{rfq_id}/invite")
async def invite_suppliers(
    rfq_id: str,
    data: InviteSuppliersRequest,
    ctx: Annotated[BuyerContext, Depends(require_buyer_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await RfqService(db).invite_suppliers(rfq_id, ctx.actor.id, data.supplier_ids)
