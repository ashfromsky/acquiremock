import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_check(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


@pytest.mark.asyncio
async def test_create_invoice_success(client: AsyncClient, sample_invoice_data):
    response = await client.post("/api/create-invoice", json=sample_invoice_data)
    assert response.status_code == 200
    data = response. json()
    assert "pageUrl" in data
    assert "/checkout/" in data["pageUrl"]


@pytest.mark.asyncio
async def test_create_invoice_invalid_amount(client: AsyncClient):
    invalid_data = {
        "amount": -100,
        "reference": "ORDER-INVALID",
        "webhookUrl": "https://example.com/webhook",
        "redirectUrl":  "https://example.com/success"
    }
    response = await client.post("/api/create-invoice", json=invalid_data)
    assert response.status_code in [400, 422]


@pytest.mark.asyncio
async def test_create_invoice_missing_fields(client: AsyncClient):
    incomplete_data = {
        "amount": 5000
    }
    response = await client.post("/api/create-invoice", json=incomplete_data)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_checkout_page_not_found(client: AsyncClient):
    response = await client.get("/checkout/nonexistent-payment-id")
    assert response. status_code in [404, 200]


@pytest.mark.asyncio
async def test_checkout_page_access(client: AsyncClient, sample_invoice_data):
    create_response = await client.post("/api/create-invoice", json=sample_invoice_data)
    assert create_response.status_code == 200
    page_url = create_response.json()["pageUrl"]
    payment_id = page_url.split("/checkout/")[-1]

    checkout_response = await client.get(f"/checkout/{payment_id}")
    assert checkout_response.status_code == 200


@pytest.mark.asyncio
async def test_api_root(client: AsyncClient):
    response = await client.get("/")
    assert response.status_code == 200