from io import BytesIO

import pytest

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


@pytest.mark.asyncio
async def test_rfq_attachment_is_copied_to_contract(
    client, buyer_auth, supplier_auth
):
    if not buyer_auth["actor_id"] or not supplier_auth["actor_id"]:
        pytest.skip("Missing actor fixtures")

    rfq_id = await _create_draft_rfq(client, buyer_auth, "RFQ with attachment")

    upload_res = await client.post(
        f"{API}/buyer/rfqs/{rfq_id}/attachments",
        headers=buyer_auth["headers"],
        files={"file": ("brief.pdf", BytesIO(b"%PDF-1.4 test brief"), "application/pdf")},
    )
    assert upload_res.status_code == 200, upload_res.text

    rfq_res = await client.get(
        f"{API}/buyer/rfqs/{rfq_id}",
        headers=buyer_auth["headers"],
    )
    assert rfq_res.status_code == 200, rfq_res.text
    rfq_attachments = rfq_res.json()["attachments"]
    assert len(rfq_attachments) == 1
    source = rfq_attachments[0]
    assert source["file_name"] == "brief.pdf"
    assert source["file_type"] == "application/pdf"

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
            "message": "Готовы выполнить контракт",
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
    contract_id = accept_res.json()["contract_id"]

    contract_res = await client.get(
        f"{API}/buyer/contracts/{contract_id}",
        headers=buyer_auth["headers"],
    )
    assert contract_res.status_code == 200, contract_res.text
    files = contract_res.json()["files"]
    assert len(files) == 1
    copied = files[0]
    assert copied["file_name"] == source["file_name"]
    assert copied["file_type"] == source["file_type"]
    assert copied["file_url"] == source["file_url"]
