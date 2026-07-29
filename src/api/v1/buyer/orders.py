from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.deps import BuyerContext, require_buyer_ctx
from src.db.session import get_db
from src.modules.orders.schemas import CreateMarketplaceOrderRequest, MarketplaceOrderSchema
from src.modules.orders.service import OrderService

router = APIRouter(prefix="/orders", tags=["buyer-orders"])


@router.post("", response_model=MarketplaceOrderSchema)
async def create_order(
    data: CreateMarketplaceOrderRequest,
    ctx: Annotated[BuyerContext, Depends(require_buyer_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await OrderService(db).create_order(ctx.actor.id, data)


@router.get("", response_model=list[MarketplaceOrderSchema])
async def list_orders(
    ctx: Annotated[BuyerContext, Depends(require_buyer_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await OrderService(db).list_for_buyer(ctx.actor.id)


@router.get("/{order_id}", response_model=MarketplaceOrderSchema)
async def get_order(
    order_id: str,
    ctx: Annotated[BuyerContext, Depends(require_buyer_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await OrderService(db).get_for_buyer(order_id, ctx.actor.id)


@router.post("/{order_id}/cancel", response_model=MarketplaceOrderSchema)
async def cancel_order(
    order_id: str,
    ctx: Annotated[BuyerContext, Depends(require_buyer_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await OrderService(db).cancel_order(order_id, ctx.actor.id)


@router.post("/{order_id}/offers/{offer_id}/accept", response_model=MarketplaceOrderSchema)
async def accept_offer(
    order_id: str,
    offer_id: str,
    ctx: Annotated[BuyerContext, Depends(require_buyer_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await OrderService(db).accept_offer(order_id, offer_id, ctx.actor.id)
