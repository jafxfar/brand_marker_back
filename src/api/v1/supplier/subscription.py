from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.deps import SupplierContext, require_supplier_ctx
from src.db.session import get_db
from src.modules.subscription.schemas import ActivateSubscriptionRequest, SubscriptionResponse
from src.modules.subscription.service import SubscriptionService

router = APIRouter(prefix="/subscription", tags=["supplier-subscription"])


@router.get("", response_model=SubscriptionResponse)
async def get_subscription(
    ctx: Annotated[SupplierContext, Depends(require_supplier_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await SubscriptionService(db).get_subscription(ctx.user.id)


@router.post("/activate", response_model=SubscriptionResponse)
async def activate_subscription(
    data: ActivateSubscriptionRequest,
    ctx: Annotated[SupplierContext, Depends(require_supplier_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await SubscriptionService(db).activate(ctx.user.id, data.plan)


@router.post("/cancel", response_model=SubscriptionResponse)
async def cancel_subscription(
    ctx: Annotated[SupplierContext, Depends(require_supplier_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await SubscriptionService(db).cancel(ctx.user.id)
