import pytest

API = "/api/v1"


@pytest.mark.asyncio
async def test_buyer_reviews_list(client, buyer_auth):
    if not buyer_auth["actor_id"]:
        pytest.skip("No buyer actor")
    res = await client.get(f"{API}/buyer/reviews/", headers=buyer_auth["headers"])
    assert res.status_code == 200
    assert isinstance(res.json(), list)


@pytest.mark.asyncio
async def test_public_rfqs(client):
    res = await client.get(f"{API}/public/rfqs")
    assert res.status_code == 200
    assert isinstance(res.json(), list)


@pytest.mark.asyncio
async def test_public_catalog(client):
    res = await client.get(f"{API}/public/catalog")
    assert res.status_code == 200
    assert isinstance(res.json(), list)


@pytest.mark.asyncio
async def test_buyer_rfqs_list(client, buyer_auth):
    if not buyer_auth["actor_id"]:
        pytest.skip("No buyer actor")
    res = await client.get(f"{API}/buyer/rfqs/", headers=buyer_auth["headers"])
    assert res.status_code == 200
    assert isinstance(res.json(), list)


@pytest.mark.asyncio
async def test_public_suppliers_category_filter(client):
    res = await client.get(f"{API}/public/suppliers?category=it")
    assert res.status_code == 200
    assert isinstance(res.json(), list)
