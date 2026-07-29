import pytest


@pytest.mark.asyncio
async def test_admin_can_list_users(client, admin_auth):
    res = await client.get("/api/v1/admin/users", headers=admin_auth["headers"])
    assert res.status_code == 200
    assert isinstance(res.json(), list)


@pytest.mark.asyncio
async def test_buyer_cannot_access_admin(client, buyer_auth):
    if not buyer_auth["actor_id"]:
        pytest.skip("No buyer company")
    res = await client.get("/api/v1/admin/users", headers=buyer_auth["headers"])
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_supplier_cannot_access_admin(client, supplier_auth):
    if not supplier_auth["actor_id"]:
        pytest.skip("No supplier company")
    res = await client.get("/api/v1/admin/users", headers=supplier_auth["headers"])
    assert res.status_code == 403
