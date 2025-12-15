import pytest
from datetime import datetime
from app.models.main_models import (
    Payment,
    PaymentStatus,
    SuccessfulOperation,
    SavedCard,
    WebhookLog
)
from app.models.errors import (
    PaymentError,
    PaymentNotFoundError,
    PaymentAlreadyProcessedError,
    PaymentExpiredError,
    InsufficientFundsError,
    InvalidOTPError
)


def test_payment_status_values():
    assert PaymentStatus. PENDING. value == "pending"
    assert PaymentStatus.PAID.value == "paid"
    assert PaymentStatus.FAILED. value == "failed"


def test_payment_error_base():
    error = PaymentError(
        code="TEST_ERROR",
        message="Test error message",
        status_code=400,
        payment_id="pay_123"
    )
    assert error.code == "TEST_ERROR"
    assert error.message == "Test error message"
    assert error.status_code == 400
    assert error.payment_id == "pay_123"


def test_payment_not_found_error():
    error = PaymentNotFoundError("pay_404")
    assert error.code == "PAYMENT_NOT_FOUND"
    assert error.status_code == 404
    assert "pay_404" in error.message


def test_payment_already_processed_error():
    error = PaymentAlreadyProcessedError("pay_409")
    assert error.code == "PAYMENT_ALREADY_PROCESSED"
    assert error.status_code == 409


def test_payment_expired_error():
    error = PaymentExpiredError("pay_410")
    assert error.code == "PAYMENT_EXPIRED"
    assert error.status_code == 410


def test_insufficient_funds_error():
    error = InsufficientFundsError("pay_402")
    assert error.code == "INSUFFICIENT_FUNDS"
    assert error.status_code == 402


def test_invalid_otp_error():
    error = InvalidOTPError("pay_401")
    assert error.code == "INVALID_OTP"
    assert error.status_code == 401


def test_successful_operation_model():
    operation = SuccessfulOperation(
        payment_id="pay_success",
        email="test@example.com",
        amount=10000,
        reference="ORDER-123",
        card_mask="**** **** **** 1111",
        redirect_url="https://example.com/success"
    )
    assert operation.payment_id == "pay_success"
    assert operation.email == "test@example. com"
    assert operation.amount == 10000


def test_saved_card_model():
    card = SavedCard(
        email="user@example.com",
        card_token="tok_123456",
        card_hash="hash_abc",
        cvv_hash="cvv_hash",
        expiry="12/25",
        card_mask="**** **** **** 4242"
    )
    assert card.email == "user@example. com"
    assert card.psp_provider == "mock"


def test_webhook_log_model():
    log = WebhookLog(
        payment_id="pay_webhook",
        webhook_url="https://example.com/webhook",
        payload='{"status": "paid"}',
        signature="sig_123",
        attempt_number=1
    )
    assert log.payment_id == "pay_webhook"
    assert log. success == False
    assert log.attempt_number == 1