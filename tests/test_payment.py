import pytest
from httpx import AsyncClient
from datetime import datetime, timedelta

from app.models.main_models import Payment, PaymentStatus
from app.security.crypto import generate_secure_otp, hash_sensitive_data, verify_sensitive_data


@pytest.mark.asyncio
async def test_payment_creation_flow(client: AsyncClient, sample_invoice_data):
    response = await client.post("/api/create-invoice", json=sample_invoice_data)
    assert response.status_code == 200
    data = response.json()
    assert "pageUrl" in data


@pytest.mark.asyncio
async def test_payment_status_enum():
    assert PaymentStatus.PENDING == "pending"
    assert PaymentStatus.WAITING_FOR_OTP == "waiting_for_otp"
    assert PaymentStatus.PAID == "paid"
    assert PaymentStatus.FAILED == "failed"
    assert PaymentStatus.EXPIRED == "expired"
    assert PaymentStatus.REFUNDED == "refunded"


@pytest.mark.asyncio
async def test_payment_model_defaults():
    payment = Payment(
        id="test-payment-123",
        amount=10000,
        reference="ORDER-TEST",
        webhook_url="https://example.com/webhook",
        redirect_url="https://example.com/success"
    )
    assert payment. status == PaymentStatus.PENDING
    assert payment.webhook_attempts == 0
    assert payment.otp_code is None
    assert payment.card_mask is None


@pytest. mark.asyncio
async def test_payment_expiry_time():
    payment = Payment(
        id="test-payment-456",
        amount=5000,
        reference="ORDER-EXPIRY",
        webhook_url="https://example.com/webhook",
        redirect_url="https://example.com/success"
    )
    assert payment.expires_at > datetime.utcnow()
    assert payment.expires_at < datetime.utcnow() + timedelta(minutes=20)


def test_otp_generation():
    otp = generate_secure_otp()
    assert len(otp) == 4
    assert otp.isdigit()


def test_otp_generation_custom_length():
    otp = generate_secure_otp(length=6)
    assert len(otp) == 6
    assert otp.isdigit()


def test_password_hashing():
    password = "test_password_123"
    hashed = hash_sensitive_data(password)
    assert hashed != password
    assert verify_sensitive_data(password, hashed)


def test_password_verification_fails_wrong_password():
    password = "correct_password"
    wrong_password = "wrong_password"
    hashed = hash_sensitive_data(password)
    assert not verify_sensitive_data(wrong_password, hashed)


@pytest.mark.asyncio
async def test_multiple_invoices_creation(client: AsyncClient):
    for i in range(3):
        invoice_data = {
            "amount": 1000 * (i + 1),
            "reference": f"ORDER-MULTI-{i}",
            "webhookUrl": "https://example.com/webhook",
            "redirectUrl": "https://example.com/success"
        }
        response = await client.post("/api/create-invoice", json=invoice_data)
        assert response.status_code == 200
        assert "pageUrl" in response.json()