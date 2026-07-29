import pytest

API = "/api/v1"


@pytest.mark.asyncio
async def test_individual_buyer_can_create_rfq(client, buyer_auth):
    if not buyer_auth["actor_id"]:
        pytest.skip("No buyer actor")
    me = buyer_auth["me"]
    individual = next((a for a in me["actors"] if a["kind"] == "individual" and a["side"] == "buyer"), None)
    if not individual:
        pytest.skip("No individual buyer actor")
    headers = {**buyer_auth["headers"], "X-Actor-Id": str(individual["id"])}
    res = await client.post(
        f"{API}/buyer/rfqs/",
        headers=headers,
        json={
            "type": "service",
            "title": "Individual RFQ test",
            "category_id": "it",
            "budget_type": "open",
            "currency": "RUB",
            "deadline": "2026-12-31",
            "visibility": "public",
            "status": "draft",
            "project_duration": "2 months",
            "start_date": "2026-07-01",
        },
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["actor_id"] == str(individual["id"])


@pytest.mark.asyncio
async def test_activate_supplier_role(client, buyer_auth):
    token = buyer_auth["token"]
    headers = {"Authorization": f"Bearer {token}"}
    res = await client.post(
        f"{API}/auth/activate-role",
        headers=headers,
        json={"side": "supplier"},
    )
    assert res.status_code == 200, res.text
    me = res.json()
    assert me["capabilities"]["supplier"] is True
    supplier_actor = next((a for a in me["actors"] if a["side"] == "supplier"), None)
    assert supplier_actor is not None


@pytest.mark.asyncio
async def test_invalid_actor_header_does_not_break_me(client, buyer_auth):
    headers = {
        **buyer_auth["headers"],
        "X-Actor-Id": "999999",
    }
    res = await client.get(f"{API}/auth/me", headers=headers)
    assert res.status_code == 200, res.text
    me = res.json()
    assert me["active_actor_id"] is not None
    assert me["active_actor_id"] != 999999
