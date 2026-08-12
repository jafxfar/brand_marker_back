import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.db.session import AsyncSessionLocal
from src.models import (
    Contract,
    ContractStatus,
    Dispute,
    DisputeStatus,
    PaymentMilestone,
    PaymentMilestoneStatus,
    PaymentPlan,
)

API = "/api/v1"


async def _create_draft_rfq(client, buyer_auth, title: str) -> str:
    res = await client.post(
        f"{API}/buyer/rfqs/",
        headers=buyer_auth["headers"],
        json={
            "type": "service",
            "title": title,
            "category_id": "it",
            "budget_type": "open",
            "currency": "TJS",
            "deadline": "2026-12-31",
            "visibility": "public",
            "status": "draft",
            "project_duration": "2 months",
            "start_date": "2026-07-01",
        },
    )
    assert res.status_code == 200, res.text
    return res.json()["id"]


async def _create_contract(client, buyer_auth, supplier_auth, title: str) -> int:
    rfq_id = await _create_draft_rfq(client, buyer_auth, title)
    publish_res = await client.post(
        f"{API}/buyer/rfqs/{rfq_id}/publish",
        headers=buyer_auth["headers"],
    )
    assert publish_res.status_code == 200, publish_res.text

    proposal_res = await client.post(
        f"{API}/supplier/rfqs/{rfq_id}/proposals",
        headers=supplier_auth["headers"],
        json={
            "price": 15000,
            "currency": "TJS",
            "delivery_time": "14 days",
            "message": "Готовы выполнить контракт для спора",
        },
    )
    assert proposal_res.status_code == 200, proposal_res.text
    proposal_id = proposal_res.json()["id"]

    accept_res = await client.post(
        f"{API}/buyer/proposals/{proposal_id}/accept",
        headers=buyer_auth["headers"],
        json={"payment_type": "full_prepayment"},
    )
    assert accept_res.status_code == 200, accept_res.text
    return accept_res.json()["contract_id"]


async def _open_dispute(client, buyer_auth, contract_id: int, reason: str) -> None:
    res = await client.post(
        f"{API}/buyer/contracts/{contract_id}/dispute",
        headers=buyer_auth["headers"],
        json={"reason": reason},
    )
    assert res.status_code == 200, res.text


@pytest.mark.asyncio
async def test_open_dispute_creates_dispute_with_statement(
    client, buyer_auth, supplier_auth
):
    if not buyer_auth["actor_id"] or not supplier_auth["actor_id"]:
        pytest.skip("Missing actor fixtures")

    contract_id = await _create_contract(
        client, buyer_auth, supplier_auth, "Dispute open statement"
    )
    await _open_dispute(
        client,
        buyer_auth,
        contract_id,
        "Работа не соответствует описанию заявки",
    )

    async with AsyncSessionLocal() as db:
        dispute = (
            await db.execute(
                select(Dispute).where(Dispute.contract_id == contract_id)
            )
        ).scalar_one()
        assert dispute.status == DisputeStatus.open
        assert dispute.buyer_statement == "Работа не соответствует описанию заявки"
        assert dispute.supplier_statement is None
        contract = (
            await db.execute(select(Contract).where(Contract.id == contract_id))
        ).scalar_one()
        assert contract.status == ContractStatus.disputed


@pytest.mark.asyncio
async def test_admin_list_and_detail_disputes(
    client, admin_auth, buyer_auth, supplier_auth
):
    if not buyer_auth["actor_id"] or not supplier_auth["actor_id"]:
        pytest.skip("Missing actor fixtures")

    contract_id = await _create_contract(
        client, buyer_auth, supplier_auth, "Admin dispute list"
    )
    await _open_dispute(
        client,
        buyer_auth,
        contract_id,
        "Срыв сроков по контракту более двух недель",
    )

    async with AsyncSessionLocal() as db:
        dispute_id = (
            await db.execute(
                select(Dispute.id).where(Dispute.contract_id == contract_id)
            )
        ).scalar_one()

    list_res = await client.get(
        f"{API}/admin/disputes",
        params={"view": "open", "query": "Admin dispute", "page_size": 10},
        headers=admin_auth["headers"],
    )
    assert list_res.status_code == 200, list_res.text
    data = list_res.json()
    assert data["view_counts"]["open"] >= 1
    assert any(item["id"] == dispute_id for item in data["items"])

    detail_res = await client.get(
        f"{API}/admin/disputes/{dispute_id}",
        headers=admin_auth["headers"],
    )
    assert detail_res.status_code == 200, detail_res.text
    detail = detail_res.json()
    assert detail["buyer_statement"]
    assert isinstance(detail["evidence"], list)
    assert isinstance(detail["files"], list)
    assert isinstance(detail["messages"], list)
    assert isinstance(detail["timeline"], list)
    assert "held" in detail["escrow"]
    assert detail["contract"]["id"] == contract_id


@pytest.mark.asyncio
async def test_admin_dispute_actions(
    client, admin_auth, buyer_auth, supplier_auth
):
    if not buyer_auth["actor_id"] or not supplier_auth["actor_id"]:
        pytest.skip("Missing actor fixtures")

    release_id = await _create_contract(
        client, buyer_auth, supplier_auth, "Release dispute"
    )
    refund_id = await _create_contract(
        client, buyer_auth, supplier_auth, "Refund dispute"
    )
    partial_id = await _create_contract(
        client, buyer_auth, supplier_auth, "Partial dispute"
    )
    evidence_id = await _create_contract(
        client, buyer_auth, supplier_auth, "Evidence dispute"
    )
    close_id = await _create_contract(
        client, buyer_auth, supplier_auth, "Close dispute"
    )

    for contract_id in (release_id, refund_id, partial_id, evidence_id, close_id):
        await _open_dispute(
            client,
            buyer_auth,
            contract_id,
            "Причина открытия спора для административного решения",
        )

    async with AsyncSessionLocal() as db:
        for contract_id in (release_id, refund_id, partial_id):
            result = await db.execute(
                select(Contract)
                .where(Contract.id == contract_id)
                .options(
                    selectinload(Contract.payment_plan).selectinload(
                        PaymentPlan.milestones
                    )
                )
            )
            contract = result.scalar_one()
            for milestone in contract.payment_plan.milestones:
                milestone.status = PaymentMilestoneStatus.disputed
        await db.commit()

        async def dispute_for(contract_id: int) -> int:
            return (
                await db.execute(
                    select(Dispute.id).where(Dispute.contract_id == contract_id)
                )
            ).scalar_one()

        release_dispute = await dispute_for(release_id)
        refund_dispute = await dispute_for(refund_id)
        partial_dispute = await dispute_for(partial_id)
        evidence_dispute = await dispute_for(evidence_id)
        close_dispute = await dispute_for(close_id)

    evidence_res = await client.post(
        f"{API}/admin/disputes/{evidence_dispute}/action",
        json={"action": "request_evidence", "reason": "Нужны фото и акты"},
        headers=admin_auth["headers"],
    )
    assert evidence_res.status_code == 200, evidence_res.text
    assert evidence_res.json()["status"] == "under_review"

    release_res = await client.post(
        f"{API}/admin/disputes/{release_dispute}/action",
        json={"action": "release_funds", "reason": "Работа выполнена"},
        headers=admin_auth["headers"],
    )
    assert release_res.status_code == 200, release_res.text
    assert release_res.json()["status"] == "resolved"
    assert release_res.json()["contract_status"] == "completed"

    refund_res = await client.post(
        f"{API}/admin/disputes/{refund_dispute}/action",
        json={"action": "refund_buyer", "reason": "Поставщик не выполнил условия"},
        headers=admin_auth["headers"],
    )
    assert refund_res.status_code == 200, refund_res.text
    assert refund_res.json()["contract_status"] == "cancelled"

    partial_res = await client.post(
        f"{API}/admin/disputes/{partial_dispute}/action",
        json={
            "action": "partial_refund",
            "reason": "Частичное исполнение",
            "partial_buyer_amount": 7500,
        },
        headers=admin_auth["headers"],
    )
    assert partial_res.status_code == 200, partial_res.text
    assert partial_res.json()["resolution"] == "partial_refund"

    close_res = await client.post(
        f"{API}/admin/disputes/{close_dispute}/action",
        json={"action": "close_case", "reason": "Стороны договорились"},
        headers=admin_auth["headers"],
    )
    assert close_res.status_code == 200, close_res.text
    assert close_res.json()["status"] == "resolved"

    list_resolved = await client.get(
        f"{API}/admin/disputes",
        params={"view": "resolved"},
        headers=admin_auth["headers"],
    )
    assert list_resolved.status_code == 200
    resolved_ids = {item["id"] for item in list_resolved.json()["items"]}
    assert release_dispute in resolved_ids
    assert close_dispute in resolved_ids

    list_review = await client.get(
        f"{API}/admin/disputes",
        params={"view": "under_review"},
        headers=admin_auth["headers"],
    )
    assert any(
        item["id"] == evidence_dispute for item in list_review.json()["items"]
    )

    async with AsyncSessionLocal() as db:
        release_milestones = (
            await db.execute(
                select(PaymentMilestone).where(
                    PaymentMilestone.contract_id == release_id
                )
            )
        ).scalars().all()
        assert all(
            m.status == PaymentMilestoneStatus.released for m in release_milestones
        )
        refund_milestones = (
            await db.execute(
                select(PaymentMilestone).where(
                    PaymentMilestone.contract_id == refund_id
                )
            )
        ).scalars().all()
        assert all(
            m.status == PaymentMilestoneStatus.refunded for m in refund_milestones
        )


@pytest.mark.asyncio
async def test_buyer_cannot_access_admin_disputes(client, buyer_auth):
    if not buyer_auth["actor_id"]:
        pytest.skip("No buyer actor")
    res = await client.get(
        f"{API}/admin/disputes",
        headers=buyer_auth["headers"],
    )
    assert res.status_code == 403
