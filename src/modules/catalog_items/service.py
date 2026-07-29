from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.exceptions import ForbiddenError, NotFoundError
from src.models import (
    CatalogItem,
    CatalogItemType,
    Category,
    ItemAttribute,
    ItemMedia,
    ItemMediaType,
    ItemPricing,
    ItemStats,
    ItemStatus,
    PricingType,
)
from src.modules.catalog_items.schemas import (
    CatalogItemInput,
    CatalogItemWithRelations,
    CategoryRefSchema,
    ItemStatsSchema,
)


def _item_to_schema(item: CatalogItem) -> CatalogItemWithRelations:
    category = None
    if item.category_id:
        pass
    return CatalogItemWithRelations(
        id=item.id,
        actor_id=item.actor_id,
        type=item.type.value,
        category_id=item.category_id,
        title=item.title,
        description=item.description,
        status=item.status.value,
        created_at=item.created_at,
        category=CategoryRefSchema(
            id=item.category.id,
            parent_id=item.category.parent_id,
            name=item.category.name,
            slug=item.category.slug,
        )
        if hasattr(item, "category") and item.category
        else None,
        attributes=[
            {
                "id": a.id,
                "item_id": a.item_id,
                "name": a.name,
                "value": a.value,
                "value_type": a.value_type,
                "sort_order": a.sort_order,
            }
            for a in item.attributes
        ],
        pricing={
            "id": item.pricing.id,
            "item_id": item.pricing.item_id,
            "pricing_type": item.pricing.pricing_type.value,
            "currency": item.pricing.currency,
            "fixed_price": item.pricing.fixed_price,
            "hourly_rate": item.pricing.hourly_rate,
            "monthly_rate": item.pricing.monthly_rate,
            "tiers": item.pricing.tiers or [],
        }
        if item.pricing
        else None,
        media=[
            {
                "id": m.id,
                "item_id": m.item_id,
                "file_name": m.file_name,
                "file_url": m.file_url,
                "media_type": m.media_type.value,
                "sort_order": m.sort_order,
            }
            for m in item.media
        ],
        stats=ItemStatsSchema(
            item_id=item.stats.item_id,
            views=item.stats.views,
            leads=item.stats.leads,
        )
        if item.stats
        else ItemStatsSchema(item_id=item.id, views=0, leads=0),
    )


class CatalogItemService:
    _load_options = (
        selectinload(CatalogItem.attributes),
        selectinload(CatalogItem.pricing),
        selectinload(CatalogItem.media),
        selectinload(CatalogItem.stats),
        selectinload(CatalogItem.category),
    )

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_item(self, item_id: int) -> CatalogItem:
        result = await self.db.execute(
            select(CatalogItem)
            .where(CatalogItem.id == item_id)
            .options(*self._load_options)
        )
        item = result.scalar_one_or_none()
        if not item:
            raise NotFoundError("Catalog item not found")
        return item

    async def list_for_supplier(
        self, actor_id: int, status: str | None = None
    ) -> list[CatalogItemWithRelations]:
        stmt = (
            select(CatalogItem)
            .where(CatalogItem.actor_id == actor_id)
            .options(*self._load_options)
            .order_by(CatalogItem.created_at.desc())
        )
        if status:
            stmt = stmt.where(CatalogItem.status == ItemStatus(status))
        result = await self.db.execute(stmt)
        return [_item_to_schema(i) for i in result.scalars().all()]

    async def list_active_for_company_actor(self, actor_id: int) -> list[CatalogItemWithRelations]:
        stmt = (
            select(CatalogItem)
            .where(CatalogItem.actor_id == actor_id, CatalogItem.status == ItemStatus.active)
            .options(*self._load_options)
            .order_by(CatalogItem.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return [_item_to_schema(i) for i in result.scalars().all()]

    async def list_public(
        self, query: str | None = None, category_slug: str | None = None
    ) -> list[CatalogItemWithRelations]:
        stmt = (
            select(CatalogItem)
            .join(Category, CatalogItem.category_id == Category.id)
            .where(CatalogItem.status == ItemStatus.active)
            .options(*self._load_options)
            .order_by(CatalogItem.created_at.desc())
            .limit(100)
        )
        if query:
            pattern = f"%{query}%"
            stmt = stmt.where(
                CatalogItem.title.ilike(pattern) | CatalogItem.description.ilike(pattern)
            )
        if category_slug:
            stmt = stmt.where(Category.slug == category_slug)
        result = await self.db.execute(stmt)
        return [_item_to_schema(i) for i in result.scalars().unique().all()]

    async def get_public(self, item_id: int) -> CatalogItemWithRelations:
        item = await self._get_item(item_id)
        if item.status != ItemStatus.active:
            raise NotFoundError("Catalog item not found")
        return _item_to_schema(item)

    async def get(self, item_id: int, actor_id: int) -> CatalogItemWithRelations:
        item = await self._get_item(item_id)
        if item.actor_id != actor_id:
            raise ForbiddenError("Access denied")
        return _item_to_schema(item)

    async def create(self, actor_id: int, data: CatalogItemInput) -> CatalogItemWithRelations:
        item = CatalogItem(
            actor_id=actor_id,
            type=CatalogItemType(data.type),
            category_id=data.category_id,
            title=data.title,
            description=data.description or None,
            status=ItemStatus(data.status),
        )
        self.db.add(item)
        await self.db.flush()

        for idx, attr in enumerate(data.attributes):
            self.db.add(
                ItemAttribute(
                    item_id=item.id,
                    name=attr.name,
                    value=attr.value,
                    value_type=attr.value_type,
                    sort_order=attr.sort_order or idx,
                )
            )

        self.db.add(
            ItemPricing(
                item_id=item.id,
                pricing_type=PricingType(data.pricing.pricing_type),
                currency=data.pricing.currency,
                fixed_price=data.pricing.fixed_price,
                hourly_rate=data.pricing.hourly_rate,
                monthly_rate=data.pricing.monthly_rate,
                tiers=[t.model_dump() for t in data.pricing.tiers],
            )
        )

        for idx, m in enumerate(data.media):
            self.db.add(
                ItemMedia(
                    item_id=item.id,
                    file_name=m.file_name,
                    file_url=m.file_url,
                    media_type=ItemMediaType(m.media_type),
                    sort_order=m.sort_order or idx,
                )
            )

        self.db.add(ItemStats(item_id=item.id, views=0, leads=0))
        await self.db.flush()
        return await self.get(item.id, actor_id)

    async def update(
        self, item_id: int, actor_id: int, data: CatalogItemInput
    ) -> CatalogItemWithRelations:
        item = await self._get_item(item_id)
        if item.actor_id != actor_id:
            raise ForbiddenError("Access denied")

        item.type = CatalogItemType(data.type)
        item.category_id = data.category_id
        item.title = data.title
        item.description = data.description or None
        item.status = ItemStatus(data.status)

        for attr in list(item.attributes):
            await self.db.delete(attr)
        for idx, attr in enumerate(data.attributes):
            self.db.add(
                ItemAttribute(
                    item_id=item.id,
                    name=attr.name,
                    value=attr.value,
                    value_type=attr.value_type,
                    sort_order=attr.sort_order or idx,
                )
            )

        if item.pricing:
            await self.db.delete(item.pricing)
        self.db.add(
            ItemPricing(
                item_id=item.id,
                pricing_type=PricingType(data.pricing.pricing_type),
                currency=data.pricing.currency,
                fixed_price=data.pricing.fixed_price,
                hourly_rate=data.pricing.hourly_rate,
                monthly_rate=data.pricing.monthly_rate,
                tiers=[t.model_dump() for t in data.pricing.tiers],
            )
        )

        for m in list(item.media):
            await self.db.delete(m)
        for idx, m in enumerate(data.media):
            self.db.add(
                ItemMedia(
                    item_id=item.id,
                    file_name=m.file_name,
                    file_url=m.file_url,
                    media_type=ItemMediaType(m.media_type),
                    sort_order=m.sort_order or idx,
                )
            )

        await self.db.flush()
        return await self.get(item.id, actor_id)

    async def set_status(
        self, item_id: int, actor_id: int, status: ItemStatus
    ) -> CatalogItemWithRelations:
        item = await self._get_item(item_id)
        if item.actor_id != actor_id:
            raise ForbiddenError("Access denied")
        item.status = status
        await self.db.flush()
        return await self.get(item.id, actor_id)

    async def delete(self, item_id: int, actor_id: int) -> None:
        item = await self._get_item(item_id)
        if item.actor_id != actor_id:
            raise ForbiddenError("Access denied")
        await self.db.delete(item)
