from typing import Annotated

from fastapi import APIRouter, Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.deps import BuyerContext, FINANCE_ROLES, require_buyer_ctx, require_buyer_company_roles
from src.db.session import get_db
from src.modules.payments.service import PaymentService

router = APIRouter(prefix="/payments", tags=["buyer-payments"])


@router.get("/contracts/{contract_id}/milestones")
async def get_milestones(
    contract_id: int,
    ctx: Annotated[BuyerContext, Depends(require_buyer_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await PaymentService(db).get_milestones(contract_id, ctx.actor.id)


@router.post("/milestones/{milestone_id}/fund")
async def fund_milestone(
    milestone_id: int,
    ctx: Annotated[BuyerContext, Depends(require_buyer_company_roles(*FINANCE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_db)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    milestone = await PaymentService(db).fund_milestone(
        milestone_id, ctx.actor.id, idempotency_key
    )
    return {"id": milestone.id, "status": milestone.status.value}


@router.post("/milestones/{milestone_id}/approve")
async def approve_milestone(
    milestone_id: int,
    ctx: Annotated[BuyerContext, Depends(require_buyer_company_roles(*FINANCE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    milestone = await PaymentService(db).approve_milestone(milestone_id, ctx.actor.id)
    return {"id": milestone.id, "status": milestone.status.value}


@router.post("/mock/confirm/{milestone_id}")
async def mock_confirm_payment(
    milestone_id: int,
    ctx: Annotated[BuyerContext, Depends(require_buyer_company_roles(*FINANCE_ROLES))],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await PaymentService(db).mock_confirm_payment(milestone_id, ctx.actor.id)


@router.get("/history")
async def payment_history(
    ctx: Annotated[BuyerContext, Depends(require_buyer_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await PaymentService(db).payment_history(ctx.actor.id)


@router.get("/pending")
async def pending_payments(
    ctx: Annotated[BuyerContext, Depends(require_buyer_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    items = await PaymentService(db).pending_payments(ctx.actor.id)
    return {"count": len(items), "items": items}
