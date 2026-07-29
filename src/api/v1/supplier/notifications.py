from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.deps import SupplierContext, require_supplier_ctx
from src.db.session import get_db
from src.modules.notifications.schemas import NotificationSchema
from src.modules.notifications.service import NotificationService

router = APIRouter(prefix="/notifications", tags=["supplier-notifications"])


@router.get("/", response_model=list[NotificationSchema])
async def list_notifications(
    ctx: Annotated[SupplierContext, Depends(require_supplier_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return [
        NotificationSchema(
            id=n.id,
            type=n.type.value,
            title=n.title,
            body=n.body,
            href=n.href,
            read=n.read,
            created_at=n.created_at,
        )
        for n in await NotificationService(db).list_for_user(ctx.user.id)
    ]


@router.patch("/{notification_id}/read")
async def mark_read(
    notification_id: int,
    ctx: Annotated[SupplierContext, Depends(require_supplier_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    n = await NotificationService(db).mark_read(notification_id, ctx.user.id)
    return {"id": n.id if n else notification_id, "read": True}


@router.post("/read-all", status_code=204)
async def mark_all_read(
    ctx: Annotated[SupplierContext, Depends(require_supplier_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await NotificationService(db).mark_all_read(ctx.user.id)
