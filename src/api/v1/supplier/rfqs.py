from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.deps import SupplierContext, require_supplier_ctx
from src.db.session import get_db
from src.modules.proposals.schemas import ProposalCreate
from src.modules.proposals.service import ProposalService
from src.modules.rfqs.service import RfqService

router = APIRouter(prefix="/rfqs", tags=["supplier-rfqs"])


@router.get("/board")
async def rfq_board(
    ctx: Annotated[SupplierContext, Depends(require_supplier_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await RfqService(db).list_board_for_supplier(ctx.actor.id)


@router.get("/{rfq_id}")
async def get_rfq(
    rfq_id: str,
    ctx: Annotated[SupplierContext, Depends(require_supplier_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await RfqService(db).get(rfq_id, supplier_id=ctx.actor.id)


@router.post("/{rfq_id}/proposals")
async def submit_proposal(
    rfq_id: str,
    data: ProposalCreate,
    ctx: Annotated[SupplierContext, Depends(require_supplier_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await ProposalService(db).submit(rfq_id, ctx.actor.id, data)
