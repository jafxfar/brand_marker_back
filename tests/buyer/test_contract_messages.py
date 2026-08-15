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
    return accept_res.json()["contract_id"]


def _message_texts(payload: dict) -> list[str]:
    messages = (payload.get("conversation") or {}).get("messages") or []
    return [item["text"] for item in messages]


@pytest.mark.asyncio
async def test_buyer_consecutive_messages_are_returned_in_response(
    client, buyer_auth, supplier_auth
):
    if not buyer_auth["actor_id"] or not supplier_auth["actor_id"]:
        pytest.skip("Missing actor fixtures")

    contract_id = await _create_contract(
        client, buyer_auth, supplier_auth, "Chat lag RFQ"
    )

    first_res = await client.post(
        f"{API}/buyer/contracts/{contract_id}/messages",
        headers=buyer_auth["headers"],
        json={"text": "привет"},
    )
    assert first_res.status_code == 200, first_res.text
    first_texts = _message_texts(first_res.json())
    assert "привет" in first_texts

    second_res = await client.post(
        f"{API}/buyer/contracts/{contract_id}/messages",
        headers=buyer_auth["headers"],
        json={"text": "как дела"},
    )
    assert second_res.status_code == 200, second_res.text
    second_texts = _message_texts(second_res.json())
    assert "привет" in second_texts
    assert "как дела" in second_texts
