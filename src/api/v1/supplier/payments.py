from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.deps import SupplierContext, require_supplier_ctx
from src.db.session import get_db
from src.modules.payments.service import PaymentService

router = APIRouter(prefix="/payments", tags=["supplier-payments"])


@router.get("/contracts/{contract_id}/milestones")
async def get_milestones(
    contract_id: int,
    ctx: Annotated[SupplierContext, Depends(require_supplier_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await PaymentService(db).get_milestones(contract_id, ctx.actor.id)


@router.get("/history")
async def payment_history(
    ctx: Annotated[SupplierContext, Depends(require_supplier_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await PaymentService(db).supplier_payment_history(ctx.actor.id)


@router.get("/pending")
async def pending_payouts(
    ctx: Annotated[SupplierContext, Depends(require_supplier_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    items = await PaymentService(db).supplier_pending_payouts(ctx.actor.id)
    return {"count": len(items), "items": items}


@router.get("/balance")
async def supplier_balance(
    ctx: Annotated[SupplierContext, Depends(require_supplier_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await PaymentService(db).supplier_balance(ctx.actor.id)
