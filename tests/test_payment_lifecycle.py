import asyncio
from datetime import timedelta

import pytest
from fastapi import BackgroundTasks
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, select

from app.core.limiter import limiter
from app.core.time import utcnow
from app.database.core.session import get_db
from app.functional.main_functions import get_expired_payments, get_payment
from app.main_test import app
from app.models.main_models import Payment, PaymentStatus, SuccessfulOperation
from app.services.payments.lifecycle import (
    expire_overdue_payments,
    finalize_successful_payment,
)


async def test_concurrent_otp_submissions_finalize_payment_once(tmp_path, monkeypatch):
    async def fake_dispatch_webhook(payment_id: str, timeout: int = 10) -> bool:
        return True

    async def fake_send_receipt(to_email: str, payment_data: dict):
        return None

    monkeypatch.setattr("app.services.webhook_service.dispatch_webhook", fake_dispatch_webhook)
    monkeypatch.setattr("app.services.smtp_service.send_receipt_email", fake_send_receipt)

    db_file = tmp_path / "concurrent_otp.db"
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
                id="pay-conc-otp",
                amount=9000,
                reference="ORD-CONC-OTP",
                webhook_url="https://example.com/hook",
                redirect_url="https://example.com/ok",
                status=PaymentStatus.WAITING_FOR_OTP.value,
                otp_email="buyer@example.com",
                otp_code="4821",
                otp_expires_at=utcnow() + timedelta(minutes=5),
                card_mask="**** 4444",
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
            otp_get = await c.get("/otp/pay-conc-otp")
            csrf = otp_get.cookies["csrf_token"]
            payload = {"otp_code": "4821", "csrf_token": csrf}

            r1, r2 = await asyncio.gather(
                c.post("/otp/verify/pay-conc-otp", data=payload, follow_redirects=False),
                c.post("/otp/verify/pay-conc-otp", data=payload, follow_redirects=False),
            )
    finally:
        app.dependency_overrides.clear()

    statuses = sorted([r1.status_code, r2.status_code])
    assert statuses == [303, 409]

    async with session_factory() as verify_session:
        payment = await get_payment(verify_session, "pay-conc-otp")
        assert payment.status == PaymentStatus.PAID.value
        assert payment.otp_code is None
        ops = (
            await verify_session.execute(
                select(SuccessfulOperation).where(
                    SuccessfulOperation.payment_id == "pay-conc-otp"
                )
            )
        ).scalars().all()
        assert len(ops) == 1

    await engine.dispose()


async def test_finalization_rolls_back_and_skips_side_effects_on_db_error(
    db_session,
    monkeypatch,
):
    payment = Payment(
        id="pay-atomic-err",
        amount=7500,
        reference="ORD-ATOMIC-ERR",
        webhook_url="https://example.com/hook",
        redirect_url="https://example.com/ok",
        status=PaymentStatus.WAITING_FOR_OTP.value,
        otp_email="atomic@example.com",
        otp_code="9999",
        otp_expires_at=utcnow() + timedelta(minutes=5),
        card_mask="**** 4444",
    )
    db_session.add(payment)
    await db_session.commit()

    async def failing_commit():
        raise RuntimeError("Simulated commit failure")

    monkeypatch.setattr(db_session, "commit", failing_commit)

    bg = BackgroundTasks()
    with pytest.raises(RuntimeError, match="Simulated commit failure"):
        await finalize_successful_payment(payment, db_session, bg)

    assert len(bg.tasks) == 0

    monkeypatch.undo()
    db_session.expire_all()
    persisted = await get_payment(db_session, "pay-atomic-err")
    assert persisted.status == PaymentStatus.WAITING_FOR_OTP.value
    assert persisted.paid_at is None
    ops = (
        await db_session.execute(
            select(SuccessfulOperation).where(SuccessfulOperation.payment_id == "pay-atomic-err")
        )
    ).scalars().all()
    assert ops == []


async def test_expiration_includes_waiting_for_otp_and_is_idempotent(
    client: AsyncClient,
    db_session,
):
    past = utcnow() - timedelta(minutes=2)
    future = utcnow() + timedelta(minutes=10)

    p_pending = Payment(
        id="pay-exp-pend",
        amount=1000,
        reference="ORD-EXP-PEND",
        webhook_url="https://example.com/hook",
        redirect_url="https://example.com/ok",
        status=PaymentStatus.PENDING.value,
        expires_at=past,
    )
    p_otp = Payment(
        id="pay-exp-otp",
        amount=2000,
        reference="ORD-EXP-OTP",
        webhook_url="https://example.com/hook",
        redirect_url="https://example.com/ok",
        status=PaymentStatus.WAITING_FOR_OTP.value,
        otp_email="exp@example.com",
        otp_code="1234",
        otp_expires_at=future,
        expires_at=past,
    )
    p_active = Payment(
        id="pay-active",
        amount=3000,
        reference="ORD-ACTIVE",
        webhook_url="https://example.com/hook",
        redirect_url="https://example.com/ok",
        status=PaymentStatus.WAITING_FOR_OTP.value,
        otp_email="act@example.com",
        otp_code="5678",
        expires_at=future,
    )
    db_session.add_all([p_pending, p_otp, p_active])
    await db_session.commit()

    expired_list = await get_expired_payments(db_session)
    assert {p.id for p in expired_list} == {"pay-exp-pend", "pay-exp-otp"}

    count = await expire_overdue_payments(db_session)
    assert count == 2
    assert await expire_overdue_payments(db_session) == 0

    db_session.expire_all()
    p_otp_after = await get_payment(db_session, "pay-exp-otp")
    assert p_otp_after.status == PaymentStatus.EXPIRED.value
    assert p_otp_after.otp_code is None
    assert p_otp_after.otp_expires_at is None

    p_active_after = await get_payment(db_session, "pay-active")
    assert p_active_after.status == PaymentStatus.WAITING_FOR_OTP.value
