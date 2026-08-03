from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.deps import get_current_user
from src.db.session import get_db
from src.models import User
from src.modules.catalog_items.schemas import CatalogItemReportCreate, CatalogItemReportResponse
from src.modules.catalog_items.service import CatalogItemService

router = APIRouter(prefix="/catalog", tags=["catalog"])


@router.post(
    "/items/{item_id}/reports",
    response_model=CatalogItemReportResponse,
)
async def create_catalog_item_report(
    item_id: int,
    data: CatalogItemReportCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
):
    return await CatalogItemService(db).create_report(item_id, current_user, data)
