from datetime import timedelta

import pytest
from httpx import AsyncClient
from sqlmodel import select

from app.core.time import utcnow
from app.functional.main_functions import get_payment
from app.models.main_models import AuthChallenge, Payment, PaymentStatus
from app.services.authentication.customer_auth import cleanup_expired_auth_challenges


@pytest.fixture(autouse=True)
def mock_outbound_calls(monkeypatch):
    async def fake_send_otp(to_email: str, otp_code: str):
        return None

    async def fake_send_receipt(to_email: str, payment_data: dict):
        return None

    async def fake_dispatch_webhook(payment_id: str, timeout: int = 10) -> bool:
        return True

    monkeypatch.setattr("app.api.routes.payments.send_otp_email", fake_send_otp)
    monkeypatch.setattr("app.api.routes.pages.send_otp_email", fake_send_otp)
    monkeypatch.setattr("app.services.smtp_service.send_receipt_email", fake_send_receipt)
    monkeypatch.setattr("app.services.webhook_service.dispatch_webhook", fake_dispatch_webhook)


async def test_payment_otp_locks_after_five_invalid_attempts(client: AsyncClient, db_session):
    payment = Payment(
        id="pay-otp-lock",
        amount=5000,
        reference="ORD-OTP-LOCK",
        webhook_url="https://example.com/hook",
        redirect_url="https://example.com/ok",
        status=PaymentStatus.WAITING_FOR_OTP.value,
        otp_email="payer@example.com",
        otp_code="7391",
        otp_expires_at=utcnow() + timedelta(minutes=5),
        card_mask="**** 4444",
    )
    db_session.add(payment)
    await db_session.commit()

    otp_page = await client.get("/otp/pay-otp-lock")
    assert otp_page.status_code == 200
    csrf = otp_page.cookies["csrf_token"]

    for idx in range(4):
        resp = await client.post(
            "/otp/verify/pay-otp-lock",
            data={"otp_code": "0000", "csrf_token": csrf},
        )
        assert resp.status_code == 401
        assert resp.json()["error"] == "INVALID_OTP"
        db_session.expire_all()
        updated = await get_payment(db_session, "pay-otp-lock")
        assert updated.otp_attempts == idx + 1

    fifth = await client.post(
        "/otp/verify/pay-otp-lock",
        data={"otp_code": "0000", "csrf_token": csrf},
    )
    assert fifth.status_code == 429
    assert fifth.json()["error"] == "OTP_MAX_ATTEMPTS_EXCEEDED"

    db_session.expire_all()
    locked_payment = await get_payment(db_session, "pay-otp-lock")
    assert locked_payment.status == PaymentStatus.FAILED.value
    assert locked_payment.otp_code is None
    assert locked_payment.otp_attempts == 5

    replay_valid_code = await client.post(
        "/otp/verify/pay-otp-lock",
        data={"otp_code": "7391", "csrf_token": csrf},
    )
    assert replay_valid_code.status_code == 409


async def test_payment_otp_expiration_and_resend_reset(client: AsyncClient, db_session):
    payment = Payment(
        id="pay-otp-exp",
        amount=4000,
        reference="ORD-OTP-EXP",
        webhook_url="https://example.com/hook",
        redirect_url="https://example.com/ok",
        status=PaymentStatus.WAITING_FOR_OTP.value,
        otp_email="payer@example.com",
        otp_code="1122",
        otp_attempts=3,
        otp_expires_at=utcnow() - timedelta(seconds=10),
        card_mask="**** 4444",
    )
    db_session.add(payment)
    await db_session.commit()

    otp_page = await client.get("/otp/pay-otp-exp")
    csrf = otp_page.cookies["csrf_token"]

    expired_otp = await client.post(
        "/otp/verify/pay-otp-exp",
        data={"otp_code": "1122", "csrf_token": csrf},
    )
    assert expired_otp.status_code == 401
    assert expired_otp.json()["error"] == "INVALID_OTP"

    resend = await client.post(
        "/otp/resend/pay-otp-exp",
        data={"csrf_token": csrf},
        follow_redirects=False,
    )
    assert resend.status_code == 303

    db_session.expire_all()
    refreshed = await get_payment(db_session, "pay-otp-exp")
    assert refreshed.otp_attempts == 0
    assert refreshed.otp_resend_count == 1
    assert refreshed.otp_code is not None
    assert refreshed.otp_expires_at is not None and refreshed.otp_expires_at > utcnow()

    ok = await client.post(
        "/otp/verify/pay-otp-exp",
        data={"otp_code": refreshed.otp_code, "csrf_token": csrf},
        follow_redirects=False,
    )
    assert ok.status_code == 303

    reuse = await client.post(
        "/otp/verify/pay-otp-exp",
        data={"otp_code": refreshed.otp_code, "csrf_token": csrf},
    )
    assert reuse.status_code == 409


async def test_cleanup_expired_auth_challenges(db_session):
    now = utcnow()
    db_session.add(
        AuthChallenge(
            email="expired@example.com",
            code_hash="hash1",
            attempts=0,
            expires_at=now - timedelta(minutes=1),
        )
    )
    db_session.add(
        AuthChallenge(
            email="active@example.com",
            code_hash="hash2",
            attempts=0,
            expires_at=now + timedelta(minutes=5),
        )
    )
    await db_session.commit()

    removed = await cleanup_expired_auth_challenges(db_session)
    assert removed == 1

    remaining = (await db_session.execute(select(AuthChallenge))).scalars().all()
    assert [c.email for c in remaining] == ["active@example.com"]
