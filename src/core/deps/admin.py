from typing import Annotated

from fastapi import Depends

from src.core.deps.auth import get_current_user
from src.core.exceptions import ForbiddenError
from src.models import User, UserRole

ADMIN_ROLES = {UserRole.admin, UserRole.superadmin, UserRole.moderator}


async def require_admin(
    user: Annotated[User, Depends(get_current_user)],
) -> User:
    if user.role not in ADMIN_ROLES:
        raise ForbiddenError("Admin access required")
    return user
