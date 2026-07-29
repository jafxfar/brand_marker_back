from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Actor, ActorKind, CompanyUser, Notification, NotificationType, Proposal, Rfq
from src.modules.notifications.schemas import NotificationSchema
from src.modules.notifications.ws_manager import notification_ws_manager


class NotificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def resolve_actor_recipients(
        self, actor_id: int
    ) -> list[tuple[int, int | None]]:
        result = await self.db.execute(select(Actor).where(Actor.id == actor_id))
        actor = result.scalar_one_or_none()
        if not actor:
            return []

        if actor.kind == ActorKind.individual:
            if actor.user_id is None:
                return []
            return [(actor.user_id, None)]

        if actor.company_id is None:
            return []

        members = await self.db.execute(
            select(CompanyUser).where(CompanyUser.company_id == actor.company_id)
        )
        return [(m.user_id, actor.company_id) for m in members.scalars().all()]

    def _to_schema(self, notification: Notification) -> NotificationSchema:
        return NotificationSchema(
            id=notification.id,
            type=notification.type.value,
            title=notification.title,
            body=notification.body,
            href=notification.href,
            read=notification.read,
            created_at=notification.created_at,
        )

    async def _push_created(self, notifications: list[Notification]) -> None:
        if not notifications:
            return
        user_ids = list({n.user_id for n in notifications})
        for notification in notifications:
            await notification_ws_manager.broadcast_to_users(
                [notification.user_id],
                {
                    "event": "notification.created",
                    "data": self._to_schema(notification).model_dump(mode="json"),
                },
            )

    async def notify_actor_members(
        self,
        actor_id: int,
        ntype: NotificationType,
        title: str,
        body: str,
        href: str | None = None,
    ) -> list[Notification]:
        recipients = await self.resolve_actor_recipients(actor_id)
        created: list[Notification] = []
        for user_id, company_id in recipients:
            notification = Notification(
                user_id=user_id,
                company_id=company_id,
                type=ntype,
                title=title,
                body=body,
                href=href,
            )
            self.db.add(notification)
            created.append(notification)
        if created:
            await self.db.flush()
            await self._push_created(created)
        return created

    async def notify_rfq_owner(
        self, rfq: Rfq, title: str, body: str, href: str | None = None
    ) -> list[Notification]:
        return await self.notify_actor_members(
            rfq.actor_id,
            NotificationType.proposal,
            title,
            body,
            href or f"/customer/rfqs/{rfq.id}/proposals",
        )

    async def notify_supplier_on_accept(
        self, proposal: Proposal, contract_id: int
    ) -> list[Notification]:
        rfq = proposal.rfq
        return await self.notify_actor_members(
            proposal.supplier_actor_id,
            NotificationType.contract,
            "Предложение принято",
            f"Заказчик принял ваше предложение на RFQ «{rfq.title}»",
            f"/supplier/contracts/{contract_id}",
        )

    async def notify_user(
        self,
        user_id: int,
        ntype: NotificationType,
        title: str,
        body: str,
        href: str | None = None,
        company_id: int | None = None,
    ) -> Notification:
        notification = Notification(
            user_id=user_id,
            company_id=company_id,
            type=ntype,
            title=title,
            body=body,
            href=href,
        )
        self.db.add(notification)
        await self.db.flush()
        await self._push_created([notification])
        return notification

    async def list_for_user(self, user_id: int) -> list[Notification]:
        result = await self.db.execute(
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
        )
        return list(result.scalars().all())

    async def mark_read(self, notification_id: int, user_id: int) -> Notification | None:
        result = await self.db.execute(
            select(Notification).where(
                Notification.id == notification_id, Notification.user_id == user_id
            )
        )
        notification = result.scalar_one_or_none()
        if notification:
            notification.read = True
            await self.db.flush()
        return notification

    async def mark_all_read(self, user_id: int) -> None:
        result = await self.db.execute(
            select(Notification).where(Notification.user_id == user_id, Notification.read == False)
        )
        for notification in result.scalars().all():
            notification.read = True
        await self.db.flush()
