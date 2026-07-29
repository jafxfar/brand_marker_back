from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.deps import SupplierContext, require_supplier_ctx
from src.db.session import get_db
from src.modules.orders.schemas import CreateOrderOfferRequest, MarketplaceOrderSchema
from src.modules.orders.service import OrderService

router = APIRouter(prefix="/orders", tags=["supplier-orders"])


@router.get("", response_model=list[MarketplaceOrderSchema])
async def list_orders(
    ctx: Annotated[SupplierContext, Depends(require_supplier_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
    tab: Literal["available", "responded", "deals"] = Query("available"),
):
    svc = OrderService(db)
    if tab == "available":
        return await svc.list_available_for_supplier(ctx.actor.id)
    if tab == "responded":
        return await svc.list_responded_for_supplier(ctx.actor.id)
    return await svc.list_deals_for_supplier(ctx.actor.id)


@router.get("/customers")
async def list_customers(
    ctx: Annotated[SupplierContext, Depends(require_supplier_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await OrderService(db).list_customers_for_supplier(ctx.actor.id)


@router.get("/{order_id}", response_model=MarketplaceOrderSchema)
async def get_order(
    order_id: str,
    ctx: Annotated[SupplierContext, Depends(require_supplier_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await OrderService(db).get_for_supplier(order_id, ctx.actor.id)


@router.post("/{order_id}/offers", response_model=MarketplaceOrderSchema)
async def submit_offer(
    order_id: str,
    data: CreateOrderOfferRequest,
    ctx: Annotated[SupplierContext, Depends(require_supplier_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    supplier_name = ctx.company.title if ctx.company else None
    return await OrderService(db).submit_offer(
        order_id, ctx.actor.id, supplier_name, data
    )
