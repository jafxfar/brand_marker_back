from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import CompanyUser, Notification, NotificationType, Rfq, User


class NotificationService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def notify_rfq_owner(self, rfq: Rfq, title: str, body: str, href: str | None = None) -> None:
        result = await self.db.execute(
            select(CompanyUser).where(CompanyUser.company_id == rfq.actor_id)
        )
        for membership in result.scalars().all():
            self.db.add(
                Notification(
                    user_id=membership.user_id,
                    company_id=rfq.actor_id,
                    type=NotificationType.proposal,
                    title=title,
                    body=body,
                    href=href or f"/customer/rfqs/{rfq.id}/proposals",
                )
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
        n = Notification(
            user_id=user_id,
            company_id=company_id,
            type=ntype,
            title=title,
            body=body,
            href=href,
        )
        self.db.add(n)
        await self.db.flush()
        return n

    async def list_for_user(self, user_id: int) -> list[Notification]:
        result = await self.db.execute(
            select(Notification)
            .where(Notification.user_id == user_id)
            .order_by(Notification.created_at.desc())
        )
        return list(result.scalars().all())

    async def mark_read(self, notification_id: int, user_id: int) -> Notification:
        result = await self.db.execute(
            select(Notification).where(
                Notification.id == notification_id, Notification.user_id == user_id
            )
        )
        n = result.scalar_one_or_none()
        if n:
            n.read = True
            await self.db.flush()
        return n

    async def mark_all_read(self, user_id: int) -> None:
        result = await self.db.execute(
            select(Notification).where(Notification.user_id == user_id, Notification.read == False)
        )
        for n in result.scalars().all():
            n.read = True
        await self.db.flush()
