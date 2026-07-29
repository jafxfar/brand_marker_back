from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.deps import SupplierContext, require_supplier_ctx
from src.db.session import get_db
from src.modules.supplier_finance.schemas import (
    InvoiceSchema,
    WithdrawalCreate,
    WithdrawalDestinationCreate,
    WithdrawalDestinationSchema,
    WithdrawalSchema,
)
from src.modules.supplier_finance.service import SupplierFinanceService

router = APIRouter(prefix="/finance", tags=["supplier-finance"])


@router.get("/destinations", response_model=list[WithdrawalDestinationSchema])
async def list_destinations(
    ctx: Annotated[SupplierContext, Depends(require_supplier_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await SupplierFinanceService(db).list_destinations(ctx.actor.id)


@router.post("/destinations", response_model=WithdrawalDestinationSchema)
async def create_destination(
    data: WithdrawalDestinationCreate,
    ctx: Annotated[SupplierContext, Depends(require_supplier_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await SupplierFinanceService(db).create_destination(ctx.actor.id, data)


@router.get("/withdrawals", response_model=list[WithdrawalSchema])
async def list_withdrawals(
    ctx: Annotated[SupplierContext, Depends(require_supplier_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await SupplierFinanceService(db).list_withdrawals(ctx.actor.id)


@router.post("/withdrawals", response_model=WithdrawalSchema)
async def request_withdrawal(
    data: WithdrawalCreate,
    ctx: Annotated[SupplierContext, Depends(require_supplier_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await SupplierFinanceService(db).request_withdrawal(ctx.actor.id, data)


@router.get("/invoices", response_model=list[InvoiceSchema])
async def list_invoices(
    ctx: Annotated[SupplierContext, Depends(require_supplier_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await SupplierFinanceService(db).list_invoices(ctx.actor.id)
