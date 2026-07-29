import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from src.models import (
    MarketplaceOrder,
    OrderKind,
    OrderOffer,
    OrderOfferStatus,
    OrderStatus,
)
from src.modules.orders.schemas import (
    CreateMarketplaceOrderRequest,
    CreateOrderOfferRequest,
    CustomerGroupSchema,
    MarketplaceOrderSchema,
    OrderOfferSchema,
)


def _order_to_schema(order: MarketplaceOrder) -> MarketplaceOrderSchema:
    return MarketplaceOrderSchema(
        id=order.id,
        buyer_actor_id=order.buyer_actor_id,
        kind=order.kind.value,
        title=order.title,
        description=order.description,
        category_id=order.category_id,
        category_label=order.category_label,
        budget=order.budget,
        qty=order.qty,
        needs_delivery=order.needs_delivery,
        status=order.status.value,
        accepted_offer_id=order.accepted_offer_id,
        created_at=order.created_at,
        offers=[
            OrderOfferSchema(
                id=o.id,
                order_id=o.order_id,
                supplier_actor_id=o.supplier_actor_id,
                supplier_name=o.supplier_name,
                price=o.price,
                message=o.message,
                delivery_days=o.delivery_days,
                status=o.status.value,
                created_at=o.created_at,
            )
            for o in order.offers
        ],
    )


class OrderService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_order(self, order_id: str) -> MarketplaceOrder:
        result = await self.db.execute(
            select(MarketplaceOrder)
            .where(MarketplaceOrder.id == order_id)
            .options(selectinload(MarketplaceOrder.offers))
        )
        order = result.scalar_one_or_none()
        if not order:
            raise NotFoundError("Order not found")
        return order

    async def create_order(
        self, buyer_actor_id: int, data: CreateMarketplaceOrderRequest
    ) -> MarketplaceOrderSchema:
        order = MarketplaceOrder(
            id=str(uuid.uuid4()),
            buyer_actor_id=buyer_actor_id,
            kind=OrderKind(data.kind),
            title=data.title,
            description=data.description,
            category_id=data.category_id,
            category_label=data.category_label,
            budget=data.budget,
            qty=data.qty,
            needs_delivery=data.needs_delivery,
            status=OrderStatus.published,
        )
        self.db.add(order)
        await self.db.flush()
        return _order_to_schema(order)

    async def list_for_buyer(self, buyer_actor_id: int) -> list[MarketplaceOrderSchema]:
        result = await self.db.execute(
            select(MarketplaceOrder)
            .where(MarketplaceOrder.buyer_actor_id == buyer_actor_id)
            .options(selectinload(MarketplaceOrder.offers))
            .order_by(MarketplaceOrder.created_at.desc())
        )
        return [_order_to_schema(o) for o in result.scalars().all()]

    async def get_for_buyer(
        self, order_id: str, buyer_actor_id: int
    ) -> MarketplaceOrderSchema:
        order = await self._get_order(order_id)
        if order.buyer_actor_id != buyer_actor_id:
            raise ForbiddenError("Access denied")
        return _order_to_schema(order)

    async def cancel_order(self, order_id: str, buyer_actor_id: int) -> MarketplaceOrderSchema:
        order = await self._get_order(order_id)
        if order.buyer_actor_id != buyer_actor_id:
            raise ForbiddenError("Access denied")
        if order.status != OrderStatus.published:
            raise ConflictError("Only published orders can be cancelled")
        order.status = OrderStatus.cancelled
        await self.db.flush()
        return _order_to_schema(await self._get_order(order_id))

    async def list_available_for_supplier(
        self, supplier_actor_id: int
    ) -> list[MarketplaceOrderSchema]:
        result = await self.db.execute(
            select(MarketplaceOrder)
            .where(MarketplaceOrder.status == OrderStatus.published)
            .options(selectinload(MarketplaceOrder.offers))
            .order_by(MarketplaceOrder.created_at.desc())
        )
        return [_order_to_schema(o) for o in result.scalars().all()]

    async def list_responded_for_supplier(
        self, supplier_actor_id: int
    ) -> list[MarketplaceOrderSchema]:
        result = await self.db.execute(
            select(MarketplaceOrder)
            .join(OrderOffer)
            .where(OrderOffer.supplier_actor_id == supplier_actor_id)
            .options(selectinload(MarketplaceOrder.offers))
            .order_by(MarketplaceOrder.created_at.desc())
        )
        return [_order_to_schema(o) for o in result.scalars().unique().all()]

    async def list_deals_for_supplier(
        self, supplier_actor_id: int
    ) -> list[MarketplaceOrderSchema]:
        result = await self.db.execute(
            select(MarketplaceOrder)
            .join(OrderOffer)
            .where(
                OrderOffer.supplier_actor_id == supplier_actor_id,
                OrderOffer.status == OrderOfferStatus.accepted,
            )
            .options(selectinload(MarketplaceOrder.offers))
            .order_by(MarketplaceOrder.created_at.desc())
        )
        return [_order_to_schema(o) for o in result.scalars().unique().all()]

    async def get_for_supplier(
        self, order_id: str, supplier_actor_id: int
    ) -> MarketplaceOrderSchema:
        return _order_to_schema(await self._get_order(order_id))

    async def submit_offer(
        self,
        order_id: str,
        supplier_actor_id: int,
        supplier_name: str | None,
        data: CreateOrderOfferRequest,
    ) -> MarketplaceOrderSchema:
        order = await self._get_order(order_id)
        if order.status != OrderStatus.published:
            raise ConflictError("Order is not open for offers")
        if any(o.supplier_actor_id == supplier_actor_id for o in order.offers):
            raise ConflictError("Offer already submitted")
        offer = OrderOffer(
            id=str(uuid.uuid4()),
            order_id=order_id,
            supplier_actor_id=supplier_actor_id,
            supplier_name=supplier_name,
            price=data.price,
            message=data.message,
            delivery_days=data.delivery_days,
            status=OrderOfferStatus.pending,
        )
        self.db.add(offer)
        await self.db.flush()
        return _order_to_schema(await self._get_order(order_id))

    async def accept_offer(
        self, order_id: str, offer_id: str, buyer_actor_id: int
    ) -> MarketplaceOrderSchema:
        order = await self._get_order(order_id)
        if order.buyer_actor_id != buyer_actor_id:
            raise ForbiddenError("Access denied")
        offer = next((o for o in order.offers if o.id == offer_id), None)
        if not offer:
            raise NotFoundError("Offer not found")
        order.status = OrderStatus.in_progress
        order.accepted_offer_id = offer_id
        offer.status = OrderOfferStatus.accepted
        for o in order.offers:
            if o.id != offer_id and o.status == OrderOfferStatus.pending:
                o.status = OrderOfferStatus.rejected
        await self.db.flush()
        return _order_to_schema(await self._get_order(order_id))

    async def list_customers_for_supplier(
        self, supplier_actor_id: int
    ) -> list[CustomerGroupSchema]:
        deals = await self.list_deals_for_supplier(supplier_actor_id)
        groups: dict[int, CustomerGroupSchema] = {}
        for order in deals:
            existing = groups.get(order.buyer_actor_id)
            if existing:
                groups[order.buyer_actor_id] = CustomerGroupSchema(
                    buyer_actor_id=order.buyer_actor_id,
                    buyer_name=existing.buyer_name,
                    order_count=existing.order_count + 1,
                    total_budget=existing.total_budget + order.budget,
                )
            else:
                groups[order.buyer_actor_id] = CustomerGroupSchema(
                    buyer_actor_id=order.buyer_actor_id,
                    buyer_name=f"Заказчик #{order.buyer_actor_id}",
                    order_count=1,
                    total_budget=order.budget,
                )
        return list(groups.values())
