from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlmodel import select

from app.functional.main_functions import get_payment
from app.models.main_models import Payment, PaymentStatus, SavedCard, SuccessfulOperation
from app.security.crypto import create_signed_email_token


@pytest.fixture(autouse=True)
def mock_outbound_calls(monkeypatch):
    async def fake_dispatch_webhook(payment_id: str, timeout: int = 10) -> bool:
        return True

    async def fake_send_otp(to_email: str, otp_code: str):
        return None

    async def fake_send_receipt(to_email: str, payment_data: dict):
        return None

    monkeypatch.setattr("app.services.webhook_service.dispatch_webhook", fake_dispatch_webhook)
    monkeypatch.setattr("app.services.smtp_service.send_otp_email", fake_send_otp)
    monkeypatch.setattr("app.services.smtp_service.send_receipt_email", fake_send_receipt)
    monkeypatch.setattr("app.api.routes.payments.send_otp_email", fake_send_otp)
    monkeypatch.setattr("app.api.routes.pages.send_otp_email", fake_send_otp)


async def test_full_payment_and_otp_flow(client: AsyncClient, db_session):
    create_resp = await client.post(
        "/api/create-invoice",
        json={
            "amount": 5000,
            "reference": "ORD-FULL-1",
            "webhookUrl": "https://example.com/hook",
            "redirectUrl": "https://example.com/done",
        },
    )
    assert create_resp.status_code == 200
    payment_id = create_resp.json()["pageUrl"].split("/")[-1]

    checkout_resp = await client.get(f"/checkout/{payment_id}")
    assert checkout_resp.status_code == 200
    csrf_token = checkout_resp.cookies["csrf_token"]

    pay_resp = await client.post(
        f"/api/pay/{payment_id}",
        data={
            "card_number": "4444 4444 4444 4444",
            "expiry": "12/30",
            "email": "buyer@example.com",
            "save_card": "true",
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )
    assert pay_resp.status_code == 303
    assert pay_resp.headers["location"] == f"/otp/{payment_id}"

    otp_get = await client.get(f"/otp/{payment_id}")
    assert otp_get.status_code == 200
    otp_csrf = otp_get.cookies["csrf_token"]

    db_session.expire_all()
    payment = await get_payment(db_session, payment_id)
    assert payment.status == PaymentStatus.WAITING_FOR_OTP
    otp_code = payment.otp_code

    verify_resp = await client.post(
        f"/otp/verify/{payment_id}",
        data={"otp_code": otp_code, "csrf_token": otp_csrf},
        follow_redirects=False,
    )
    assert verify_resp.status_code == 303
    assert verify_resp.headers["location"] == f"/success/{payment_id}"
    assert "user_session" in verify_resp.cookies

    db_session.expire_all()
    paid_payment = await get_payment(db_session, payment_id)
    assert paid_payment.status == PaymentStatus.PAID

    op = (
        await db_session.execute(
            select(SuccessfulOperation).where(SuccessfulOperation.payment_id == payment_id)
        )
    ).scalars().first()
    assert op is not None
    assert op.email == "buyer@example.com"

    saved_card = (
        await db_session.execute(select(SavedCard).where(SavedCard.email == "buyer@example.com"))
    ).scalars().first()
    assert saved_card is not None
    assert saved_card.cvv_hash == ""

    create_resp_2 = await client.post(
        "/api/create-invoice",
        json={
            "amount": 2000,
            "reference": "ORD-SAVED-2",
            "webhookUrl": "https://example.com/hook",
            "redirectUrl": "https://example.com/done",
        },
    )
    payment_id_2 = create_resp_2.json()["pageUrl"].split("/")[-1]
    checkout_2 = await client.get(f"/checkout/{payment_id_2}")
    csrf_2 = checkout_2.cookies["csrf_token"]

    client.cookies.set("user_session", create_signed_email_token("buyer@example.com"))
    pay_saved = await client.post(
        f"/api/pay/{payment_id_2}",
        data={
            "saved_card_id": str(saved_card.id),
            "email": "buyer@example.com",
            "csrf_token": csrf_2,
        },
        follow_redirects=False,
    )
    assert pay_saved.status_code == 303
    assert pay_saved.headers["location"] == f"/success/{payment_id_2}"


async def test_expired_payment_rejected_across_endpoints(client: AsyncClient, db_session):
    payment = Payment(
        id="pay-exp-1",
        amount=1000,
        reference="ORD-EXP",
        webhook_url="https://example.com/hook",
        redirect_url="https://example.com/done",
        status=PaymentStatus.PENDING,
        expires_at=datetime.utcnow() - timedelta(minutes=1),
    )
    db_session.add(payment)
    await db_session.commit()

    resp_checkout = await client.get("/checkout/pay-exp-1")
    assert resp_checkout.status_code == 410

    payment_2 = Payment(
        id="pay-exp-2",
        amount=1000,
        reference="ORD-EXP-2",
        webhook_url="https://example.com/hook",
        redirect_url="https://example.com/done",
        status=PaymentStatus.WAITING_FOR_OTP,
        otp_code="1234",
        otp_email="exp@example.com",
        expires_at=datetime.utcnow() - timedelta(minutes=1),
    )
    db_session.add(payment_2)
    await db_session.commit()

    resp_otp_get = await client.get("/otp/pay-exp-2")
    assert resp_otp_get.status_code == 410


async def test_invalid_inputs_csrf_and_otp_resend(client: AsyncClient, db_session):
    bad_amount = await client.post(
        "/api/create-invoice",
        json={
            "amount": 0,
            "reference": "ORD-ZERO",
            "webhookUrl": "https://example.com/hook",
            "redirectUrl": "https://example.com/done",
        },
    )
    assert bad_amount.status_code == 422

    payment = Payment(
        id="pay-edge-1",
        amount=1500,
        reference="ORD-EDGE",
        webhook_url="https://example.com/hook",
        redirect_url="https://example.com/done",
        status=PaymentStatus.PENDING,
    )
    db_session.add(payment)
    await db_session.commit()

    checkout = await client.get("/checkout/pay-edge-1")
    csrf = checkout.cookies["csrf_token"]

    bad_csrf = await client.post(
        "/api/pay/pay-edge-1",
        data={"card_number": "4444 4444 4444 4444", "email": "a@example.com", "csrf_token": "wrong"},
    )
    assert bad_csrf.status_code == 403
    assert bad_csrf.json()["error"] == "CSRF_TOKEN_MISMATCH"

    bad_card_id = await client.post(
        "/api/pay/pay-edge-1",
        data={"saved_card_id": "abc", "email": "a@example.com", "csrf_token": csrf},
    )
    assert bad_card_id.status_code == 400
    assert bad_card_id.json()["error"] == "INVALID_CARD"

    pay_ok = await client.post(
        "/api/pay/pay-edge-1",
        data={
            "card_number": "4444 4444 4444 4444",
            "expiry": "12/30",
            "email": "a@example.com",
            "csrf_token": csrf,
        },
        headers={"Idempotency-Key": "idem-edge-1"},
        follow_redirects=False,
    )
    assert pay_ok.status_code == 303
    assert pay_ok.headers["location"] == "/otp/pay-edge-1"

    replay = await client.post(
        "/api/pay/pay-edge-1",
        data={
            "card_number": "4444 4444 4444 4444",
            "expiry": "12/30",
            "email": "a@example.com",
            "csrf_token": csrf,
        },
        headers={"Idempotency-Key": "idem-edge-1"},
        follow_redirects=False,
    )
    assert replay.status_code == 303
    assert replay.headers["location"] == "/otp/pay-edge-1"

    otp_get = await client.get("/otp/pay-edge-1")
    otp_csrf = otp_get.cookies["csrf_token"]

    db_session.expire_all()
    p_before = await get_payment(db_session, "pay-edge-1")
    old_otp = p_before.otp_code

    resend_resp = await client.post(
        "/otp/resend/pay-edge-1",
        data={"csrf_token": otp_csrf},
        follow_redirects=False,
    )
    assert resend_resp.status_code == 303
    assert resend_resp.headers["location"] == "/otp/pay-edge-1"

    bad_otp_csrf = await client.post(
        "/otp/verify/pay-edge-1",
        data={"otp_code": old_otp, "csrf_token": "invalid"},
    )
    assert bad_otp_csrf.status_code == 403

    bad_otp = await client.post(
        "/otp/verify/pay-edge-1",
        data={"otp_code": "xxxx", "csrf_token": otp_csrf},
    )
    assert bad_otp.status_code == 401
    assert bad_otp.json()["error"] == "INVALID_OTP"

    db_session.expire_all()
    p_after = await get_payment(db_session, "pay-edge-1")
    verify_ok = await client.post(
        "/otp/verify/pay-edge-1",
        data={"otp_code": p_after.otp_code, "csrf_token": otp_csrf},
        follow_redirects=False,
    )
    assert verify_ok.status_code == 303

    already_paid = await client.post(
        "/otp/verify/pay-edge-1",
        data={"otp_code": p_after.otp_code, "csrf_token": otp_csrf},
    )
    assert already_paid.status_code == 409


async def test_insufficient_funds_marks_payment_failed(client: AsyncClient, db_session):
    payment = Payment(
        id="pay-fail-1",
        amount=1000,
        reference="ORD-FAIL",
        webhook_url="https://example.com/hook",
        redirect_url="https://example.com/done",
        status=PaymentStatus.PENDING,
    )
    db_session.add(payment)
    await db_session.commit()

    checkout = await client.get("/checkout/pay-fail-1")
    csrf = checkout.cookies["csrf_token"]

    resp = await client.post(
        "/api/pay/pay-fail-1",
        data={
            "card_number": "5555 5555 5555 5555",
            "expiry": "12/30",
            "email": "fail@example.com",
            "csrf_token": csrf,
        },
    )
    assert resp.status_code == 402
    assert resp.json()["error"] == "INSUFFICIENT_FUNDS"

    db_session.expire_all()
    updated = await get_payment(db_session, "pay-fail-1")
    assert updated.status == PaymentStatus.FAILED
