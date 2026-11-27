"""
AcquireMock Integration Example - FastAPI
==========================================

This example shows how to integrate AcquireMock payment gateway
with a FastAPI e-commerce application.

Features:
- Create payment invoices
- Handle webhook notifications
- Verify webhook signatures
- Update order status

Requirements:
    pip install fastapi uvicorn httpx sqlalchemy
"""

from fastapi import FastAPI, HTTPException, Request, Header
from pydantic import BaseModel
import httpx
import hmac
import hashlib
import json
import os
from typing import Optional
from datetime import datetime

# Configuration
ACQUIREMOCK_URL = os.getenv("ACQUIREMOCK_URL", "http://localhost:8000")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "your_webhook_secret_here")
BASE_URL = os.getenv("BASE_URL", "http://localhost:3000")

app = FastAPI(title="E-Commerce Store")

# Mock database (replace with real database)
orders_db = {}


# Models
class CreateOrderRequest(BaseModel):
    product_id: str
    quantity: int
    customer_email: str


class Order(BaseModel):
    id: str
    product_id: str
    quantity: int
    amount: int
    status: str
    customer_email: str
    payment_url: Optional[str] = None
    created_at: datetime


class WebhookPayload(BaseModel):
    payment_id: str
    reference: str
    amount: int
    status: str
    timestamp: str
    card_mask: str


# Helper functions
def calculate_order_amount(product_id: str, quantity: int) -> int:
    """Calculate order total in cents."""
    # Mock pricing (replace with real product database)
    prices = {
        "product_1": 2500,  # $25.00
        "product_2": 5000,  # $50.00
        "product_3": 10000,  # $100.00
    }
    return prices.get(product_id, 0) * quantity


def verify_webhook_signature(payload: dict, signature: str) -> bool:
    """Verify HMAC-SHA256 signature from AcquireMock."""
    message = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    expected_signature = hmac.new(
        WEBHOOK_SECRET.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected_signature, signature)


async def create_payment_invoice(order_id: str, amount: int) -> str:
    """Create payment invoice via AcquireMock API."""
    payload = {
        "amount": amount,
        "reference": order_id,
        "webhookUrl": f"{BASE_URL}/webhook/payment",
        "redirectUrl": f"{BASE_URL}/order/{order_id}/success"
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{ACQUIREMOCK_URL}/api/create-invoice",
            json=payload,
            timeout=10.0
        )
        response.raise_for_status()
        data = response.json()
        return data["pageUrl"]


# API Endpoints
@app.post("/orders", response_model=Order)
async def create_order(order_request: CreateOrderRequest):
    """
    Create a new order and generate payment link.

    Example:
        POST /orders
        {
            "product_id": "product_1",
            "quantity": 2,
            "customer_email": "customer@example.com"
        }
    """
    # Generate order ID
    order_id = f"ORDER-{datetime.now().strftime('%Y%m%d%H%M%S')}"

    # Calculate amount
    amount = calculate_order_amount(order_request.product_id, order_request.quantity)

    if amount == 0:
        raise HTTPException(status_code=404, detail="Product not found")

    # Create payment invoice
    try:
        payment_url = await create_payment_invoice(order_id, amount)
    except httpx.HTTPError as e:
        raise HTTPException(
            status_code=503,
            detail=f"Payment gateway error: {str(e)}"
        )

    # Save order to database
    order = Order(
        id=order_id,
        product_id=order_request.product_id,
        quantity=order_request.quantity,
        amount=amount,
        status="pending",
        customer_email=order_request.customer_email,
        payment_url=payment_url,
        created_at=datetime.now()
    )

    orders_db[order_id] = order

    return order


@app.get("/orders/{order_id}", response_model=Order)
async def get_order(order_id: str):
    """Get order details by ID."""
    order = orders_db.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


@app.post("/webhook/payment")
async def payment_webhook(
        request: Request,
        x_signature: Optional[str] = Header(None),
        x_payment_id: Optional[str] = Header(None)
):
    """
    Handle payment webhook from AcquireMock.

    This endpoint receives notifications when payment status changes.
    Always verify the signature before processing!
    """
    # Get payload
    payload = await request.json()

    # Verify signature
    if not x_signature:
        raise HTTPException(status_code=403, detail="Missing signature")

    if not verify_webhook_signature(payload, x_signature):
        raise HTTPException(status_code=403, detail="Invalid signature")

    # Parse webhook data
    webhook_data = WebhookPayload(**payload)

    # Find order
    order = orders_db.get(webhook_data.reference)
    if not order:
        # Log error but return 200 to prevent retries
        print(f"Order {webhook_data.reference} not found")
        return {"status": "ok"}

    # Update order status
    if webhook_data.status == "paid":
        order.status = "paid"
        print(f"✅ Order {order.id} marked as PAID")

        # Here you would:
        # - Send confirmation email to customer
        # - Trigger order fulfillment
        # - Update inventory
        # - Send receipt

    elif webhook_data.status == "failed":
        order.status = "failed"
        print(f"❌ Order {order.id} payment FAILED")

    elif webhook_data.status == "expired":
        order.status = "expired"
        print(f"⏰ Order {order.id} payment EXPIRED")

    # Save to database
    orders_db[order.id] = order

    # Return success response
    return {
        "status": "ok",
        "order_id": order.id,
        "processed_at": datetime.now().isoformat()
    }


@app.get("/order/{order_id}/success")
async def order_success(order_id: str):
    """Success page after payment (user redirected here)."""
    order = orders_db.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    return {
        "message": "Payment successful!",
        "order_id": order.id,
        "amount": order.amount,
        "status": order.status
    }


@app.get("/")
async def root():
    """API root with documentation links."""
    return {
        "service": "E-Commerce Store",
        "payment_gateway": "AcquireMock",
        "endpoints": {
            "create_order": "POST /orders",
            "get_order": "GET /orders/{order_id}",
            "webhook": "POST /webhook/payment"
        },
        "docs": "/docs"
    }


# Health check
@app.get("/health")
async def health():
    """Check if service is healthy."""
    # Check if AcquireMock is reachable
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{ACQUIREMOCK_URL}/health", timeout=5.0)
            gateway_healthy = response.status_code == 200
    except:
        gateway_healthy = False

    return {
        "status": "healthy",
        "payment_gateway": "healthy" if gateway_healthy else "unhealthy",
        "timestamp": datetime.now().isoformat()
    }


if __name__ == "__main__":
    import uvicorn

    print("🚀 Starting E-Commerce API...")
    print(f"📦 Orders endpoint: http://localhost:3000/orders")
    print(f"🔔 Webhook endpoint: http://localhost:3000/webhook/payment")
    print(f"📚 API Docs: http://localhost:3000/docs")
    print(f"💳 Payment Gateway: {ACQUIREMOCK_URL}")

    uvicorn.run(app, host="0.0.0.0", port=3000)