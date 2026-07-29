from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.deps import BuyerContext, require_buyer_ctx
from src.db.session import get_db
from src.modules.reviews.schemas import ReviewCreate, ReviewResponse
from src.modules.reviews.service import ReviewService

router = APIRouter(prefix="/reviews", tags=["buyer-reviews"])


@router.get("/", response_model=list[ReviewResponse])
async def list_my_reviews(
    ctx: Annotated[BuyerContext, Depends(require_buyer_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await ReviewService(db).list_for_reviewer(ctx.actor.id)


@router.post("/", response_model=ReviewResponse)
async def create_review(
    data: ReviewCreate,
    ctx: Annotated[BuyerContext, Depends(require_buyer_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await ReviewService(db).create(ctx.actor.id, data)
