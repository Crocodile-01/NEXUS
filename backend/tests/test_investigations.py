import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_create_investigation_api(async_client: AsyncClient):
    payload = {
        "target": "Microsoft",
        "target_type": "company",
        "objective": "Research AI cloud projects",
        "max_depth": 2,
        "max_tasks": 30,
        "mode": "PASSIVE_PUBLIC",
    }

    response = await async_client.post("/api/v1/investigations", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["target"] == "Microsoft"
    assert data["target_type"] == "company"
    assert data["status"] == "created"
    assert data["max_depth"] == 2
    assert len(data["tasks"]) == 1
    assert data["tasks"][0]["name"] == "Identify target: Microsoft"


@pytest.mark.asyncio
async def test_list_and_get_investigation_api(async_client: AsyncClient):
    payload = {"target": "example.com", "target_type": "domain"}
    create_resp = await async_client.post("/api/v1/investigations", json=payload)
    assert create_resp.status_code == 201
    inv_id = create_resp.json()["id"]

    # List
    list_resp = await async_client.get("/api/v1/investigations")
    assert list_resp.status_code == 200
    items = list_resp.json()
    assert len(items) >= 1

    # Get by ID
    get_resp = await async_client.get(f"/api/v1/investigations/{inv_id}")
    assert get_resp.status_code == 200
    inv = get_resp.json()
    assert inv["id"] == inv_id
    assert inv["target"] == "example.com"


@pytest.mark.asyncio
async def test_get_investigation_not_found(async_client: AsyncClient):
    response = await async_client.get("/api/v1/investigations/non-existent-uuid")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
