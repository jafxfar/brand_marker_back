from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from src.models import AuditLog


async def log_audit(
    db: AsyncSession,
    *,
    user_id: int | None,
    action: str,
    resource_type: str,
    resource_id: str,
    details: dict | None = None,
    ip_address: str | None = None,
) -> None:
    db.add(
        AuditLog(
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
            created_at=datetime.now(timezone.utc),
        )
    )
