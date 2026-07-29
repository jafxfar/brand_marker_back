from typing import Annotated

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.deps import BuyerContext, require_buyer_ctx
from src.db.session import get_db
from src.modules.contracts.schemas import DisputeRequest, MessageCreate
from src.modules.contracts.service import ContractService
from src.utils.storage import storage_service

router = APIRouter(prefix="/contracts", tags=["buyer-contracts"])


@router.get("/")
async def list_contracts(
    ctx: Annotated[BuyerContext, Depends(require_buyer_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await ContractService(db).list_for_actor(ctx.actor.id, "buyer")


@router.get("/{contract_id}")
async def get_contract(
    contract_id: int,
    ctx: Annotated[BuyerContext, Depends(require_buyer_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await ContractService(db).get(contract_id, ctx.actor.id)


@router.get("/{contract_id}/messages")
async def get_messages(
    contract_id: int,
    ctx: Annotated[BuyerContext, Depends(require_buyer_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    contract = await ContractService(db).get(contract_id, ctx.actor.id)
    return contract.get("conversation")


@router.post("/{contract_id}/messages")
async def post_message(
    contract_id: int,
    data: MessageCreate,
    ctx: Annotated[BuyerContext, Depends(require_buyer_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await ContractService(db).add_message(
        contract_id, ctx.user.id, ctx.actor.id, data
    )


@router.post("/{contract_id}/files")
async def upload_file(
    contract_id: int,
    ctx: Annotated[BuyerContext, Depends(require_buyer_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...),
):
    _, url = await storage_service.upload(file, f"contracts/{contract_id}")
    return await ContractService(db).add_file(
        contract_id,
        ctx.user.id,
        ctx.actor.id,
        file.filename or "file",
        url,
        file.content_type or "application/octet-stream",
    )


@router.post("/{contract_id}/submissions/{submission_id}/approve")
async def approve_submission(
    contract_id: int,
    submission_id: int,
    ctx: Annotated[BuyerContext, Depends(require_buyer_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await ContractService(db).approve_submission(
        contract_id, submission_id, ctx.actor.id
    )


@router.post("/{contract_id}/submissions/{submission_id}/reject")
async def reject_submission(
    contract_id: int,
    submission_id: int,
    ctx: Annotated[BuyerContext, Depends(require_buyer_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await ContractService(db).reject_submission(
        contract_id, submission_id, ctx.actor.id
    )


@router.post("/{contract_id}/dispute")
async def open_dispute(
    contract_id: int,
    data: DisputeRequest,
    ctx: Annotated[BuyerContext, Depends(require_buyer_ctx)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    return await ContractService(db).open_dispute(contract_id, ctx.actor.id, data)
