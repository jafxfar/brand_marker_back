import pytest


@pytest.mark.asyncio
async def test_admin_can_list_users(client, admin_auth):
    res = await client.get("/api/v1/admin/users", headers=admin_auth["headers"])
    assert res.status_code == 200
    data = res.json()
    assert set(data) == {
        "items",
        "total",
        "page",
        "page_size",
        "pages",
        "status_counts",
    }
    assert isinstance(data["items"], list)
    assert data["total"] >= len(data["items"])
    assert data["status_counts"]["all"] >= data["total"]


@pytest.mark.asyncio
async def test_admin_can_search_filter_and_paginate_users(client, admin_auth):
    search_res = await client.get(
        "/api/v1/admin/users",
        params={"query": "buyer@example.com", "status": "active", "page_size": 1},
        headers=admin_auth["headers"],
    )

    assert search_res.status_code == 200
    data = search_res.json()
    assert data["page"] == 1
    assert data["page_size"] == 1
    assert all(user["status"] == "active" for user in data["items"])
    assert all("buyer@example.com" in user["email"] for user in data["items"])


@pytest.mark.asyncio
async def test_admin_can_block_and_unblock_regular_user(client, admin_auth):
    users_res = await client.get(
        "/api/v1/admin/users",
        params={"query": "buyer@example.com"},
        headers=admin_auth["headers"],
    )
    user_id = users_res.json()["items"][0]["id"]

    blocked_res = await client.patch(
        f"/api/v1/admin/users/{user_id}/status",
        json={"status": "blocked"},
        headers=admin_auth["headers"],
    )
    assert blocked_res.status_code == 200
    assert blocked_res.json()["status"] == "blocked"

    active_res = await client.patch(
        f"/api/v1/admin/users/{user_id}/status",
        json={"status": "active"},
        headers=admin_auth["headers"],
    )
    assert active_res.status_code == 200
    assert active_res.json()["status"] == "active"


@pytest.mark.asyncio
async def test_admin_cannot_change_own_status(client, admin_auth):
    me_res = await client.get("/api/v1/auth/me", headers=admin_auth["headers"])
    admin_id = me_res.json()["user"]["id"]

    res = await client.patch(
        f"/api/v1/admin/users/{admin_id}/status",
        json={"status": "blocked"},
        headers=admin_auth["headers"],
    )
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_view_dashboard(client, admin_auth):
    res = await client.get("/api/v1/admin/dashboard", headers=admin_auth["headers"])

    assert res.status_code == 200
    data = res.json()
    assert set(data) == {"metrics", "recent_activity"}
    assert data["metrics"]["total_users"] >= 1
    assert data["metrics"]["total_companies"] >= 0
    assert data["metrics"]["escrow_balance"] >= 0
    assert data["metrics"]["monthly_revenue"] >= 0
    assert isinstance(data["recent_activity"], list)
    assert all(
        item["type"] in {"registration", "contract", "payment", "dispute"}
        for item in data["recent_activity"]
    )


@pytest.mark.asyncio
async def test_buyer_cannot_access_admin(client, buyer_auth):
    if not buyer_auth["actor_id"]:
        pytest.skip("No buyer company")
    res = await client.get("/api/v1/admin/users", headers=buyer_auth["headers"])
    assert res.status_code == 403

    dashboard_res = await client.get(
        "/api/v1/admin/dashboard",
        headers=buyer_auth["headers"],
    )
    assert dashboard_res.status_code == 403


@pytest.mark.asyncio
async def test_supplier_cannot_access_admin(client, supplier_auth):
    if not supplier_auth["actor_id"]:
        pytest.skip("No supplier company")
    res = await client.get("/api/v1/admin/users", headers=supplier_auth["headers"])
    assert res.status_code == 403
