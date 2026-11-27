import asyncio
from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from app.core.limiter import limiter
from app.core.time import utcnow
from app.database.core.session import get_db
from app.main_test import app
from app.models.main_models import Payment, PaymentStatus


@pytest.fixture(autouse=True)
def mock_outbound_calls(monkeypatch):
    async def fake_send_otp(to_email: str, otp_code: str):
        return None

    async def fake_send_receipt(to_email: str, payment_data: dict):
        return None

    async def fake_dispatch_webhook(payment_id: str, timeout: int = 10) -> bool:
        return True

    monkeypatch.setattr("app.api.routes.payments.send_otp_email", fake_send_otp)
    monkeypatch.setattr("app.services.smtp_service.send_receipt_email", fake_send_receipt)
    monkeypatch.setattr("app.services.webhook_service.dispatch_webhook", fake_dispatch_webhook)


async def test_idempotency_same_payment_replay_and_different_payment_conflict(
    client: AsyncClient,
    db_session,
):
    p1 = Payment(
        id="pay-idem-1",
        amount=5000,
        reference="ORD-IDEM-1",
        webhook_url="https://example.com/hook",
        redirect_url="https://example.com/ok",
        status=PaymentStatus.PENDING.value,
    )
    p2 = Payment(
        id="pay-idem-2",
        amount=6000,
        reference="ORD-IDEM-2",
        webhook_url="https://example.com/hook",
        redirect_url="https://example.com/ok",
        status=PaymentStatus.PENDING.value,
    )
    db_session.add(p1)
    db_session.add(p2)
    await db_session.commit()

    checkout1 = await client.get("/checkout/pay-idem-1")
    csrf1 = checkout1.cookies["csrf_token"]

    form_data = {
        "card_number": "4444 4444 4444 4444",
        "expiry": "12/30",
        "email": "idem@example.com",
        "csrf_token": csrf1,
    }
    first = await client.post(
        "/api/pay/pay-idem-1",
        data=form_data,
        headers={"Idempotency-Key": "idem-shared-key"},
        follow_redirects=False,
    )
    assert first.status_code == 303
    assert first.headers["location"] == "/otp/pay-idem-1"

    replay = await client.post(
        "/api/pay/pay-idem-1",
        data=form_data,
        headers={"Idempotency-Key": "idem-shared-key"},
        follow_redirects=False,
    )
    assert replay.status_code == 303
    assert replay.headers["location"] == "/otp/pay-idem-1"

    incompatible = await client.post(
        "/api/pay/pay-idem-1",
        data={**form_data, "email": "other@example.com"},
        headers={"Idempotency-Key": "idem-shared-key"},
        follow_redirects=False,
    )
    assert incompatible.status_code == 409
    assert incompatible.json()["error"] == "IDEMPOTENCY_KEY_CONFLICT"

    checkout2 = await client.get("/checkout/pay-idem-2")
    csrf2 = checkout2.cookies["csrf_token"]
    cross_payment = await client.post(
        "/api/pay/pay-idem-2",
        data={
            "card_number": "4444 4444 4444 4444",
            "expiry": "12/30",
            "email": "idem@example.com",
            "csrf_token": csrf2,
        },
        headers={"Idempotency-Key": "idem-shared-key"},
        follow_redirects=False,
    )
    assert cross_payment.status_code == 409
    assert cross_payment.json()["error"] == "IDEMPOTENCY_KEY_CONFLICT"
    assert cross_payment.json()["payment_id"] == "pay-idem-2"


async def test_idempotency_replays_failed_and_expired_outcomes(
    client: AsyncClient,
    db_session,
):
    p_fail = Payment(
        id="pay-idem-fail",
        amount=3000,
        reference="ORD-IDEM-FAIL",
        webhook_url="https://example.com/hook",
        redirect_url="https://example.com/ok",
        status=PaymentStatus.PENDING.value,
    )
    p_exp = Payment(
        id="pay-idem-exp",
        amount=3000,
        reference="ORD-IDEM-EXP",
        webhook_url="https://example.com/hook",
        redirect_url="https://example.com/ok",
        status=PaymentStatus.PENDING.value,
        expires_at=utcnow() - timedelta(minutes=2),
    )
    db_session.add(p_fail)
    db_session.add(p_exp)
    await db_session.commit()

    c1 = await client.get("/checkout/pay-idem-fail")
    csrf1 = c1.cookies["csrf_token"]
    fail_form = {
        "card_number": "5555 5555 5555 5555",
        "expiry": "12/30",
        "email": "fail@example.com",
        "csrf_token": csrf1,
    }
    resp1 = await client.post(
        "/api/pay/pay-idem-fail",
        data=fail_form,
        headers={"Idempotency-Key": "idem-fail-1"},
    )
    assert resp1.status_code == 402
    assert resp1.json()["error"] == "INSUFFICIENT_FUNDS"

    resp1_replay = await client.post(
        "/api/pay/pay-idem-fail",
        data=fail_form,
        headers={"Idempotency-Key": "idem-fail-1"},
    )
    assert resp1_replay.status_code == 402
    assert resp1_replay.json()["error"] == "INSUFFICIENT_FUNDS"

    csrf2 = "manual-csrf-token"
    client.cookies.set("csrf_token", csrf2)
    exp_form = {
        "card_number": "4444 4444 4444 4444",
        "expiry": "12/30",
        "email": "exp@example.com",
        "csrf_token": csrf2,
    }
    resp2 = await client.post(
        "/api/pay/pay-idem-exp",
        data=exp_form,
        headers={"Idempotency-Key": "idem-exp-1"},
    )
    assert resp2.status_code == 410
    assert resp2.json()["error"] == "PAYMENT_EXPIRED"

    resp2_replay = await client.post(
        "/api/pay/pay-idem-exp",
        data=exp_form,
        headers={"Idempotency-Key": "idem-exp-1"},
    )
    assert resp2_replay.status_code == 410
    assert resp2_replay.json()["error"] == "PAYMENT_EXPIRED"


async def test_idempotency_concurrent_requests_prevent_double_processing(tmp_path):
    db_file = tmp_path / "concurrent_idem.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )
    session_factory = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    async with session_factory() as session:
        session.add(
            Payment(
                id="pay-idem-conc",
                amount=4500,
                reference="ORD-CONC",
                webhook_url="https://example.com/hook",
                redirect_url="https://example.com/ok",
                status=PaymentStatus.PENDING.value,
            )
        )
        await session.commit()

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    if hasattr(limiter, "_storage"):
        limiter._storage.reset()

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            timeout=5.0,
        ) as c:
            checkout = await c.get("/checkout/pay-idem-conc")
            csrf = checkout.cookies["csrf_token"]
            payload = {
                "card_number": "4444 4444 4444 4444",
                "expiry": "12/30",
                "email": "conc@example.com",
                "csrf_token": csrf,
            }
            r1, r2 = await asyncio.gather(
                c.post(
                    "/api/pay/pay-idem-conc",
                    data=payload,
                    headers={"Idempotency-Key": "idem-conc-key"},
                    follow_redirects=False,
                ),
                c.post(
                    "/api/pay/pay-idem-conc",
                    data=payload,
                    headers={"Idempotency-Key": "idem-conc-key"},
                    follow_redirects=False,
                ),
            )
    finally:
        app.dependency_overrides.clear()
        await engine.dispose()

    statuses = sorted([r1.status_code, r2.status_code])
    assert statuses in ([303, 303], [303, 409])
    if 409 in statuses:
        conflict_resp = r1 if r1.status_code == 409 else r2
        assert conflict_resp.json()["error"] == "IDEMPOTENCY_REQUEST_IN_PROGRESS"
