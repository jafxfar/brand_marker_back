import pytest
from sqlalchemy import select

from src.core.security import hash_password
from src.db.session import AsyncSessionLocal
from src.models import Actor, AuditLog, Notification, User, UserRole, UserStatus


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
async def test_admin_can_list_search_and_view_company_details(client, admin_auth):
    list_res = await client.get(
        "/api/v1/admin/companies",
        params={"query": "ТехноСнаб", "status": "verified", "page_size": 1},
        headers=admin_auth["headers"],
    )
    assert list_res.status_code == 200, list_res.text
    data = list_res.json()
    assert data["page_size"] == 1
    assert data["status_counts"]["all"] >= data["total"]
    assert data["items"]
    assert data["items"][0]["title"] == "ТехноСнаб"

    company_id = data["items"][0]["id"]
    detail_res = await client.get(
        f"/api/v1/admin/companies/{company_id}",
        headers=admin_auth["headers"],
    )
    assert detail_res.status_code == 200, detail_res.text
    detail = detail_res.json()
    assert detail["owner"]["email"] == "supplier@example.com"
    assert isinstance(detail["members"], list)
    assert isinstance(detail["products"], list)
    assert isinstance(detail["services"], list)
    assert set(detail["verification_checklist"]) == {
        "legal_name",
        "tax_number",
        "address",
        "website",
        "certificates",
    }


@pytest.mark.asyncio
async def test_admin_company_actions_update_actors_notifications_and_audit(client, admin_auth):
    companies_res = await client.get(
        "/api/v1/admin/companies",
        params={"query": "supplier@example.com"},
        headers=admin_auth["headers"],
    )
    company_id = companies_res.json()["items"][0]["id"]

    documents_res = await client.post(
        f"/api/v1/admin/companies/{company_id}/action",
        json={"action": "request_documents", "reason": "Добавьте выписку"},
        headers=admin_auth["headers"],
    )
    assert documents_res.status_code == 200, documents_res.text
    assert documents_res.json()["verification_status"] == "needs_documents"

    block_res = await client.post(
        f"/api/v1/admin/companies/{company_id}/action",
        json={"action": "block", "reason": "Проверка безопасности"},
        headers=admin_auth["headers"],
    )
    assert block_res.status_code == 200, block_res.text
    assert block_res.json()["operational_status"] == "blocked"

    async with AsyncSessionLocal() as db:
        actors = (
            await db.execute(select(Actor).where(Actor.company_id == company_id))
        ).scalars().all()
        assert actors
        assert all(not actor.is_active for actor in actors)
        notification = (
            await db.execute(
                select(Notification)
                .where(Notification.company_id == company_id)
                .order_by(Notification.id.desc())
            )
        ).scalars().first()
        assert notification is not None
        audit = (
            await db.execute(
                select(AuditLog)
                .where(
                    AuditLog.resource_type == "company",
                    AuditLog.resource_id == str(company_id),
                )
                .order_by(AuditLog.id.desc())
            )
        ).scalars().first()
        assert audit is not None
        assert audit.action == "admin.company.block"

    reactivate_res = await client.post(
        f"/api/v1/admin/companies/{company_id}/action",
        json={"action": "reactivate"},
        headers=admin_auth["headers"],
    )
    assert reactivate_res.status_code == 200, reactivate_res.text
    assert reactivate_res.json()["operational_status"] == "active"

    approve_res = await client.post(
        f"/api/v1/admin/companies/{company_id}/action",
        json={"action": "approve"},
        headers=admin_auth["headers"],
    )
    assert approve_res.status_code == 200, approve_res.text


@pytest.mark.asyncio
async def test_company_negative_actions_require_reason(client, admin_auth):
    companies_res = await client.get(
        "/api/v1/admin/companies",
        headers=admin_auth["headers"],
    )
    company_id = companies_res.json()["items"][0]["id"]
    res = await client.post(
        f"/api/v1/admin/companies/{company_id}/action",
        json={"action": "deactivate"},
        headers=admin_auth["headers"],
    )
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_moderator_can_verify_but_cannot_block_company(client, admin_auth):
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == "moderator@example.com"))
        moderator = result.scalar_one_or_none()
        if not moderator:
            moderator = User(
                email="moderator@example.com",
                password_hash=hash_password("Moderator123!"),
                first_name="Test",
                last_name="Moderator",
                role=UserRole.moderator,
                status=UserStatus.active,
            )
            db.add(moderator)
        else:
            moderator.password_hash = hash_password("Moderator123!")
            moderator.role = UserRole.moderator
            moderator.status = UserStatus.active
        await db.commit()

    login_res = await client.post(
        "/api/v1/auth/login",
        json={"email": "moderator@example.com", "password": "Moderator123!"},
    )
    assert login_res.status_code == 200, login_res.text
    moderator_headers = {
        "Authorization": f"Bearer {login_res.json()['access_token']}",
    }
    companies_res = await client.get(
        "/api/v1/admin/companies",
        headers=moderator_headers,
    )
    assert companies_res.status_code == 200
    company_id = companies_res.json()["items"][0]["id"]

    request_res = await client.post(
        f"/api/v1/admin/companies/{company_id}/action",
        json={"action": "request_documents", "reason": "Нужна выписка"},
        headers=moderator_headers,
    )
    assert request_res.status_code == 200, request_res.text

    block_res = await client.post(
        f"/api/v1/admin/companies/{company_id}/action",
        json={"action": "block", "reason": "Недоступное действие"},
        headers=moderator_headers,
    )
    assert block_res.status_code == 403

    restore_res = await client.post(
        f"/api/v1/admin/companies/{company_id}/action",
        json={"action": "approve"},
        headers=admin_auth["headers"],
    )
    assert restore_res.status_code == 200


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

    company_action_res = await client.post(
        "/api/v1/admin/companies/1/action",
        json={"action": "approve"},
        headers=buyer_auth["headers"],
    )
    assert company_action_res.status_code == 403


@pytest.mark.asyncio
async def test_supplier_cannot_access_admin(client, supplier_auth):
    if not supplier_auth["actor_id"]:
        pytest.skip("No supplier company")
    res = await client.get("/api/v1/admin/users", headers=supplier_auth["headers"])
    assert res.status_code == 403
