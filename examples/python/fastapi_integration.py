"""Example FastAPI merchant integration with AcquireMock v2.0."""

from datetime import datetime, timezone
import hashlib
import hmac
import json
import os
from typing import Any, Dict, Optional

from fastapi import FastAPI, Header, HTTPException, Request
import httpx
from pydantic import BaseModel, Field

ACQUIREMOCK_BASE_URL = os.getenv("ACQUIREMOCK_BASE_URL", "http://localhost:8000")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "replace-with-matching-acquiremock-secret")
MERCHANT_BASE_URL = os.getenv("MERCHANT_BASE_URL", "http://localhost:8001")

app = FastAPI(title="Merchant Demo (FastAPI + AcquireMock v2.0)")

orders_db: Dict[str, Dict[str, Any]] = {}


class CreateOrderRequest(BaseModel):
    order_id: str = Field(..., min_length=1, max_length=64)
    amount_minor: int = Field(..., gt=0, description="Amount in minor currency units, e.g. 25000 = $250.00")


def verify_acquiremock_signature(payload: Dict[str, Any], signature: str, secret: str) -> bool:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    expected = hmac.new(
        secret.encode("utf-8"),
        canonical.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected, signature)


@app.post("/orders")
async def create_order(body: CreateOrderRequest):
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            f"{ACQUIREMOCK_BASE_URL}/api/create-invoice",
            json={
                "amount": body.amount_minor,
                "reference": body.order_id,
                "webhook_url": f"{MERCHANT_BASE_URL}/webhooks/acquiremock",
                "redirect_url": f"{MERCHANT_BASE_URL}/orders/{body.order_id}",
            },
        )
        response.raise_for_status()
        data = response.json()

    orders_db[body.order_id] = {
        "order_id": body.order_id,
        "amount_minor": body.amount_minor,
        "status": "pending",
        "checkout_url": data["pageUrl"],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    return orders_db[body.order_id]


@app.post("/webhooks/acquiremock")
async def acquiremock_webhook(
    request: Request,
    x_signature: Optional[str] = Header(None, alias="X-Signature"),
):
    if not x_signature:
        raise HTTPException(status_code=400, detail="Missing X-Signature header")

    payload = await request.json()
    if not verify_acquiremock_signature(payload, x_signature, WEBHOOK_SECRET):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    if payload.get("status") == "paid":
        reference = payload.get("reference")
        if reference and reference in orders_db:
            orders_db[reference]["status"] = "paid"
            orders_db[reference]["payment_id"] = payload.get("payment_id")
            orders_db[reference]["paid_at"] = datetime.now(timezone.utc).isoformat()

    return {"received": True}


@app.get("/orders/{order_id}")
async def get_order(order_id: str):
    order = orders_db.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order
