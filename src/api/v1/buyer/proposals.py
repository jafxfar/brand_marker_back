from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.deps import BuyerContext, require_buyer_ctx
from src.db.session import get_db
from src.modules.proposals.schemas import ProposalAcceptRequest
from src.modules.proposals.service import ProposalService

router = APIRouter(tags=["buyer-proposals"])


@router.get("/rfqs/{rfq_id}/proposals")
async def list_proposals(
    rfq_id: str,
    ctx: Annotated[BuyerContext, Depends(require_buyer_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await ProposalService(db).list_for_rfq(rfq_id, ctx.actor.id)


@router.post("/proposals/{proposal_id}/shortlist")
async def shortlist_proposal(
    proposal_id: int,
    ctx: Annotated[BuyerContext, Depends(require_buyer_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await ProposalService(db).shortlist(proposal_id, ctx.actor.id)


@router.post("/proposals/{proposal_id}/reject")
async def reject_proposal(
    proposal_id: int,
    ctx: Annotated[BuyerContext, Depends(require_buyer_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await ProposalService(db).reject(proposal_id, ctx.actor.id)


@router.post("/proposals/{proposal_id}/accept")
async def accept_proposal(
    proposal_id: int,
    ctx: Annotated[BuyerContext, Depends(require_buyer_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
    data: ProposalAcceptRequest | None = None,
):
    payment_type = data.payment_type if data else None
    milestones = (
        [m.model_dump() for m in data.milestones] if data and data.milestones else None
    )
    return await ProposalService(db).accept(
        proposal_id, ctx.actor.id, payment_type=payment_type, milestones=milestones
    )
