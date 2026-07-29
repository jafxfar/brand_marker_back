import pytest


@pytest.mark.asyncio
async def test_buyer_idor_foreign_rfq(client, buyer_auth):
    if not buyer_auth["actor_id"]:
        pytest.skip("No buyer company")
    res = await client.get(
        "/api/v1/buyer/rfqs/00000000-0000-0000-0000-000000000099",
        headers=buyer_auth["headers"],
    )
    assert res.status_code in (403, 404)
