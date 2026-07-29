from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.deps import SupplierContext, require_supplier_ctx
from src.db.session import get_db
from src.modules.proposals.schemas import ProposalUpdate
from src.modules.proposals.service import ProposalService

router = APIRouter(prefix="/proposals", tags=["supplier-proposals"])


@router.get("/")
async def list_my_proposals(
    ctx: Annotated[SupplierContext, Depends(require_supplier_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await ProposalService(db).list_for_supplier(ctx.actor.id)


@router.patch("/{proposal_id}")
async def update_proposal(
    proposal_id: int,
    data: ProposalUpdate,
    ctx: Annotated[SupplierContext, Depends(require_supplier_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await ProposalService(db).update_proposal(proposal_id, ctx.actor.id, data)


@router.post("/{proposal_id}/withdraw")
async def withdraw_proposal(
    proposal_id: int,
    ctx: Annotated[SupplierContext, Depends(require_supplier_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await ProposalService(db).withdraw(proposal_id, ctx.actor.id)
