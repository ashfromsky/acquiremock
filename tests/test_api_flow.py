import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_health_check(client: AsyncClient):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "currency" in data


async def test_create_invoice_success(client: AsyncClient):
    payload = {
        "amount": 5000,
        "reference": "TEST-ORDER-101",
        "webhookUrl": "https://example.com/webhook",
        "redirectUrl": "https://example.com/success"
    }

    response = await client.post("/api/create-invoice", json=payload)

    assert response.status_code == 200

    data = response.json()
    assert "pageUrl" in data
    assert "/checkout/" in data["pageUrl"]


async def test_create_invoice_invalid_data(client: AsyncClient):
    payload = {
        "reference": "TEST-ORDER-FAIL",
        "webhookUrl": "https://example.com/webhook",
    }

    response = await client.post("/api/create-invoice", json=payload)

    assert response.status_code == 422


async def test_checkout_page_load(client: AsyncClient):
    payload = {
        "amount": 10000,
        "reference": "TEST-CHECKOUT-FLOW",
        "webhookUrl": "https://example.com/hook",
        "redirectUrl": "https://example.com/ok"
    }
    create_resp = await client.post("/api/create-invoice", json=payload)
    assert create_resp.status_code == 200
    page_url = create_resp.json()["pageUrl"]

    payment_id = page_url.split("/")[-1]

    checkout_resp = await client.get(f"/checkout/{payment_id}")

    assert checkout_resp.status_code == 200
    assert "TEST-CHECKOUT-FLOW" in checkout_resp.text