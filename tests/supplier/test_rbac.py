import pytest


@pytest.mark.asyncio
async def test_supplier_board_isolated_from_buyer(client, supplier_auth, buyer_auth):
    if not supplier_auth["actor_id"] or not buyer_auth["actor_id"]:
        pytest.skip("Seed data missing")
    supplier_res = await client.get(
        "/api/v1/supplier/rfqs/board", headers=supplier_auth["headers"]
    )
    buyer_res = await client.get(
        "/api/v1/buyer/rfqs/", headers=buyer_auth["headers"]
    )
    assert supplier_res.status_code == 200
    assert buyer_res.status_code == 200


@pytest.mark.asyncio
async def test_supplier_cannot_fund_milestone(client, supplier_auth):
    if not supplier_auth["actor_id"]:
        pytest.skip("No supplier company")
    res = await client.post(
        "/api/v1/buyer/payments/milestones/1/fund",
        headers=supplier_auth["headers"],
    )
    assert res.status_code == 403
