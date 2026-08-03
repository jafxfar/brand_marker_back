import pytest
from sqlalchemy import select

from src.core.security import hash_password
from src.db.session import AsyncSessionLocal
from src.models import (
    AuditLog,
    CatalogItem,
    CatalogItemReport,
    CatalogItemReportStatus,
    ItemStatus,
    Notification,
    User,
    UserRole,
    UserStatus,
)


async def _create_pending_item(client, supplier_auth) -> int:
    categories = await client.get("/api/v1/public/categories")
    assert categories.status_code == 200
    category_id = categories.json()[0]["id"]
    create_res = await client.post(
        "/api/v1/supplier/catalog/items",
        headers=supplier_auth["headers"],
        json={
            "type": "service",
            "category_id": category_id,
            "title": "Модерация тест услуги",
            "description": "Описание тестовой услуги для модерации",
            "status": "pending_review",
            "attributes": [{"name": "Срок", "value": "3 дня", "value_type": "text"}],
            "media": [
                {
                    "file_name": "cover.jpg",
                    "file_url": "https://example.com/cover.jpg",
                    "media_type": "image",
                }
            ],
            "pricing": {
                "pricing_type": "fixed",
                "currency": "RUB",
                "fixed_price": 1500,
                "hourly_rate": None,
                "monthly_rate": None,
                "tiers": [],
            },
        },
    )
    assert create_res.status_code == 200, create_res.text
    return create_res.json()["id"]


@pytest.mark.asyncio
async def test_admin_can_list_and_view_catalog_item(client, admin_auth, supplier_auth):
    if not supplier_auth["actor_id"]:
        pytest.skip("No supplier actor")
    item_id = await _create_pending_item(client, supplier_auth)

    list_res = await client.get(
        "/api/v1/admin/catalog",
        params={"view": "draft", "query": "Модерация тест", "page_size": 5},
        headers=admin_auth["headers"],
    )
    assert list_res.status_code == 200, list_res.text
    data = list_res.json()
    assert data["view_counts"]["all"] >= data["total"]
    assert any(item["id"] == item_id for item in data["items"])

    detail_res = await client.get(
        f"/api/v1/admin/catalog/{item_id}",
        headers=admin_auth["headers"],
    )
    assert detail_res.status_code == 200, detail_res.text
    detail = detail_res.json()
    assert detail["title"] == "Модерация тест услуги"
    assert isinstance(detail["media"], list)
    assert isinstance(detail["attributes"], list)
    assert isinstance(detail["reports"], list)
    assert isinstance(detail["history"], list)


@pytest.mark.asyncio
async def test_catalog_report_and_admin_actions(client, admin_auth, supplier_auth, buyer_auth):
    if not supplier_auth["actor_id"] or not buyer_auth["actor_id"]:
        pytest.skip("Missing actor fixtures")
    item_id = await _create_pending_item(client, supplier_auth)

    approve_res = await client.post(
        f"/api/v1/admin/catalog/{item_id}/action",
        json={"action": "approve"},
        headers=admin_auth["headers"],
    )
    assert approve_res.status_code == 200, approve_res.text
    assert approve_res.json()["status"] == "active"

    own_report = await client.post(
        f"/api/v1/catalog/items/{item_id}/reports",
        json={"reason": "spam", "details": "Своя позиция"},
        headers=supplier_auth["headers"],
    )
    assert own_report.status_code == 403

    report_res = await client.post(
        f"/api/v1/catalog/items/{item_id}/reports",
        json={"reason": "misleading", "details": "Цена не соответствует"},
        headers=buyer_auth["headers"],
    )
    assert report_res.status_code == 200, report_res.text

    duplicate_res = await client.post(
        f"/api/v1/catalog/items/{item_id}/reports",
        json={"reason": "spam"},
        headers=buyer_auth["headers"],
    )
    assert duplicate_res.status_code == 409

    reported_res = await client.get(
        "/api/v1/admin/catalog",
        params={"view": "reported"},
        headers=admin_auth["headers"],
    )
    assert reported_res.status_code == 200
    assert any(item["id"] == item_id for item in reported_res.json()["items"])

    hide_res = await client.post(
        f"/api/v1/admin/catalog/{item_id}/action",
        json={"action": "hide", "reason": "Жалоба подтверждена"},
        headers=admin_auth["headers"],
    )
    assert hide_res.status_code == 200
    assert hide_res.json()["status"] == "hidden"

    async with AsyncSessionLocal() as db:
        reports = (
            await db.execute(select(CatalogItemReport).where(CatalogItemReport.item_id == item_id))
        ).scalars().all()
        assert reports
        assert all(report.status != CatalogItemReportStatus.open for report in reports)
        audit = (
            await db.execute(
                select(AuditLog)
                .where(
                    AuditLog.resource_type == "catalog_item",
                    AuditLog.resource_id == str(item_id),
                )
                .order_by(AuditLog.id.desc())
            )
        ).scalars().first()
        assert audit is not None
        assert audit.action == "admin.catalog.hide"
        notification = (
            await db.execute(
                select(Notification)
                .where(Notification.href == f"/supplier/catalog/{item_id}")
                .order_by(Notification.id.desc())
            )
        ).scalars().first()
        assert notification is not None

    request_res = await client.post(
        f"/api/v1/admin/catalog/{item_id}/action",
        json={"action": "request_changes", "reason": "Уточните описание"},
        headers=admin_auth["headers"],
    )
    assert request_res.status_code == 200
    assert request_res.json()["status"] == "changes_requested"

    delete_res = await client.post(
        f"/api/v1/admin/catalog/{item_id}/action",
        json={"action": "delete", "reason": "Повторные нарушения"},
        headers=admin_auth["headers"],
    )
    assert delete_res.status_code == 200
    assert delete_res.json()["status"] == "deleted"

    async with AsyncSessionLocal() as db:
        item = (
            await db.execute(select(CatalogItem).where(CatalogItem.id == item_id))
        ).scalar_one()
        assert item.status == ItemStatus.deleted

    public_res = await client.get(f"/api/v1/public/catalog/items/{item_id}")
    assert public_res.status_code == 404


@pytest.mark.asyncio
async def test_moderator_cannot_delete_catalog_item(client, admin_auth, supplier_auth):
    if not supplier_auth["actor_id"]:
        pytest.skip("No supplier actor")
    item_id = await _create_pending_item(client, supplier_auth)

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
    assert login_res.status_code == 200
    headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

    approve_res = await client.post(
        f"/api/v1/admin/catalog/{item_id}/action",
        json={"action": "approve"},
        headers=headers,
    )
    assert approve_res.status_code == 200

    delete_res = await client.post(
        f"/api/v1/admin/catalog/{item_id}/action",
        json={"action": "delete", "reason": "Недостаточно прав"},
        headers=headers,
    )
    assert delete_res.status_code == 403

    cleanup = await client.post(
        f"/api/v1/admin/catalog/{item_id}/action",
        json={"action": "delete", "reason": "Cleanup"},
        headers=admin_auth["headers"],
    )
    assert cleanup.status_code == 200


@pytest.mark.asyncio
async def test_negative_catalog_actions_require_reason(client, admin_auth, supplier_auth):
    if not supplier_auth["actor_id"]:
        pytest.skip("No supplier actor")
    item_id = await _create_pending_item(client, supplier_auth)
    res = await client.post(
        f"/api/v1/admin/catalog/{item_id}/action",
        json={"action": "hide"},
        headers=admin_auth["headers"],
    )
    assert res.status_code == 422
