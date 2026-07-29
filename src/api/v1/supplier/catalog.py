from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.deps import SupplierContext, require_supplier_ctx
from src.db.session import get_db
from src.models import ItemStatus
from src.modules.catalog_items.schemas import CatalogItemInput, CatalogItemWithRelations
from src.modules.catalog_items.service import CatalogItemService

router = APIRouter(prefix="/catalog", tags=["supplier-catalog"])


@router.get("/items", response_model=list[CatalogItemWithRelations])
async def list_items(
    ctx: Annotated[SupplierContext, Depends(require_supplier_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status: str | None = Query(None),
):
    return await CatalogItemService(db).list_for_supplier(ctx.actor.id, status)


@router.post("/items", response_model=CatalogItemWithRelations)
async def create_item(
    data: CatalogItemInput,
    ctx: Annotated[SupplierContext, Depends(require_supplier_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from src.modules.subscription.service import SubscriptionService

    if data.status == "active":
        await SubscriptionService(db).check_catalog_limit(ctx.user.id, ctx.actor.id)
    return await CatalogItemService(db).create(ctx.actor.id, data)


@router.get("/items/{item_id}", response_model=CatalogItemWithRelations)
async def get_item(
    item_id: int,
    ctx: Annotated[SupplierContext, Depends(require_supplier_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await CatalogItemService(db).get(item_id, ctx.actor.id)


@router.patch("/items/{item_id}", response_model=CatalogItemWithRelations)
async def update_item(
    item_id: int,
    data: CatalogItemInput,
    ctx: Annotated[SupplierContext, Depends(require_supplier_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await CatalogItemService(db).update(item_id, ctx.actor.id, data)


@router.post("/items/{item_id}/publish", response_model=CatalogItemWithRelations)
async def publish_item(
    item_id: int,
    ctx: Annotated[SupplierContext, Depends(require_supplier_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    from src.modules.subscription.service import SubscriptionService

    await SubscriptionService(db).check_catalog_limit(ctx.user.id, ctx.actor.id)
    return await CatalogItemService(db).set_status(item_id, ctx.actor.id, ItemStatus.active)


@router.post("/items/{item_id}/archive", response_model=CatalogItemWithRelations)
async def archive_item(
    item_id: int,
    ctx: Annotated[SupplierContext, Depends(require_supplier_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await CatalogItemService(db).set_status(item_id, ctx.actor.id, ItemStatus.archived)


@router.delete("/items/{item_id}", status_code=204)
async def delete_item(
    item_id: int,
    ctx: Annotated[SupplierContext, Depends(require_supplier_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    await CatalogItemService(db).delete(item_id, ctx.actor.id)
