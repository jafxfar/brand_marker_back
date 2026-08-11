from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from src.models import (
    Actor,
    ActorKind,
    CatalogItem,
    CatalogItemReport,
    CatalogItemReportReason,
    CatalogItemReportStatus,
    CatalogItemType,
    Category,
    ItemAttribute,
    ItemMedia,
    ItemMediaType,
    ItemPricing,
    ItemStats,
    ItemStatus,
    PricingType,
    User,
)
from src.modules.catalog_items.schemas import (
    CatalogItemInput,
    CatalogItemReportCreate,
    CatalogItemReportResponse,
    CatalogItemWithRelations,
    CategoryRefSchema,
    ItemStatsSchema,
)

SUPPLIER_WRITABLE_STATUSES = {
    ItemStatus.draft,
    ItemStatus.pending_review,
    ItemStatus.changes_requested,
    ItemStatus.archived,
}
SUPPLIER_EDITABLE_STATUSES = {
    ItemStatus.draft,
    ItemStatus.changes_requested,
    ItemStatus.pending_review,
    ItemStatus.active,
    ItemStatus.hidden,
    ItemStatus.archived,
}


def _item_to_schema(item: CatalogItem) -> CatalogItemWithRelations:
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
        if not item or item.status == ItemStatus.deleted:
            raise NotFoundError("Catalog item not found")
        return item

    @staticmethod
    def _normalize_supplier_status(
        requested: str,
        *,
        current: ItemStatus | None = None,
    ) -> ItemStatus:
        try:
            status = ItemStatus(requested)
        except ValueError as exc:
            raise ValidationError("Unsupported catalog item status") from exc

        if status in {ItemStatus.active, ItemStatus.hidden, ItemStatus.deleted}:
            raise ForbiddenError("Supplier cannot set this status")

        if status == ItemStatus.pending_review:
            return ItemStatus.pending_review

        if current == ItemStatus.changes_requested and status == ItemStatus.draft:
            return ItemStatus.draft

        if status not in SUPPLIER_WRITABLE_STATUSES:
            raise ForbiddenError("Supplier cannot set this status")
        return status

    async def list_for_supplier(
        self, actor_id: int, status: str | None = None
    ) -> list[CatalogItemWithRelations]:
        stmt = (
            select(CatalogItem)
            .where(
                CatalogItem.actor_id == actor_id,
                CatalogItem.status != ItemStatus.deleted,
            )
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
        status = self._normalize_supplier_status(data.status)
        item = CatalogItem(
            actor_id=actor_id,
            type=CatalogItemType(data.type),
            category_id=data.category_id,
            title=data.title,
            description=data.description or None,
            status=status,
        )
        self.db.add(item)
        await self.db.flush()
        item = await self._get_item(item.id)
        await self._replace_relations(item, data)
        await self.db.flush()
        self.db.add(ItemStats(item_id=item.id, views=0, leads=0))
        await self.db.flush()
        return await self.get(item.id, actor_id)

    async def update(
        self, item_id: int, actor_id: int, data: CatalogItemInput
    ) -> CatalogItemWithRelations:
        item = await self._get_item(item_id)
        if item.actor_id != actor_id:
            raise ForbiddenError("Access denied")
        if item.status not in SUPPLIER_EDITABLE_STATUSES:
            raise ForbiddenError("Catalog item cannot be edited in current status")

        requested = self._normalize_supplier_status(data.status, current=item.status)
        if item.status == ItemStatus.changes_requested and requested == ItemStatus.draft:
            next_status = ItemStatus.draft
        elif requested == ItemStatus.pending_review:
            next_status = ItemStatus.pending_review
        elif item.status in {
            ItemStatus.active,
            ItemStatus.hidden,
            ItemStatus.pending_review,
        } and requested == ItemStatus.draft:
            next_status = ItemStatus.draft
        elif requested == ItemStatus.archived:
            next_status = ItemStatus.archived
        else:
            next_status = requested if requested in SUPPLIER_WRITABLE_STATUSES else ItemStatus.draft

        item.type = CatalogItemType(data.type)
        item.category_id = data.category_id
        item.title = data.title
        item.description = data.description or None
        item.status = next_status
        await self._replace_relations(item, data)
        await self.db.flush()
        return await self.get(item.id, actor_id)

    async def _replace_relations(self, item: CatalogItem, data: CatalogItemInput) -> None:
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

        for media in list(item.media):
            await self.db.delete(media)
        for idx, media in enumerate(data.media):
            self.db.add(
                ItemMedia(
                    item_id=item.id,
                    file_name=media.file_name,
                    file_url=media.file_url,
                    media_type=ItemMediaType(media.media_type),
                    sort_order=media.sort_order or idx,
                )
            )

    async def set_status(
        self, item_id: int, actor_id: int, status: ItemStatus
    ) -> CatalogItemWithRelations:
        item = await self._get_item(item_id)
        if item.actor_id != actor_id:
            raise ForbiddenError("Access denied")
        if status == ItemStatus.active:
            item.status = ItemStatus.pending_review
        elif status == ItemStatus.archived:
            item.status = ItemStatus.archived
        elif status == ItemStatus.draft:
            item.status = ItemStatus.draft
        else:
            raise ForbiddenError("Supplier cannot set this status")
        await self.db.flush()
        return await self.get(item.id, actor_id)

    async def delete(self, item_id: int, actor_id: int) -> None:
        item = await self._get_item(item_id)
        if item.actor_id != actor_id:
            raise ForbiddenError("Access denied")
        item.status = ItemStatus.deleted
        await self.db.flush()

    async def create_report(
        self,
        item_id: int,
        reporter: User,
        data: CatalogItemReportCreate,
    ) -> CatalogItemReportResponse:
        item = await self._get_item(item_id)
        if item.status != ItemStatus.active:
            raise ValidationError("Only active catalog items can be reported")

        actor_result = await self.db.execute(select(Actor).where(Actor.id == item.actor_id))
        actor = actor_result.scalar_one_or_none()
        if actor:
            if actor.kind == ActorKind.individual and actor.user_id == reporter.id:
                raise ForbiddenError("Cannot report your own catalog item")
            if actor.kind == ActorKind.company and actor.company_id:
                from src.models import Company

                company_result = await self.db.execute(
                    select(Company).where(Company.id == actor.company_id)
                )
                company = company_result.scalar_one_or_none()
                if company and company.owner_id == reporter.id:
                    raise ForbiddenError("Cannot report your own catalog item")

        existing = await self.db.execute(
            select(CatalogItemReport).where(
                CatalogItemReport.item_id == item_id,
                CatalogItemReport.reporter_user_id == reporter.id,
                CatalogItemReport.status == CatalogItemReportStatus.open,
            )
        )
        if existing.scalar_one_or_none():
            raise ConflictError("You already have an open report for this item")

        report = CatalogItemReport(
            item_id=item_id,
            reporter_user_id=reporter.id,
            reason=CatalogItemReportReason(data.reason),
            details=data.details.strip() if data.details else None,
            status=CatalogItemReportStatus.open,
        )
        self.db.add(report)
        await self.db.flush()
        return CatalogItemReportResponse(
            id=report.id,
            item_id=report.item_id,
            reason=report.reason.value,
            details=report.details,
            status=report.status.value,
            created_at=report.created_at,
        )
