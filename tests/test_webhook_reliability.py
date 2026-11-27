import asyncio
import socket
from datetime import timedelta

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel, select

import app.database.core.session as db_session_module
from app.core.time import utcnow
from app.functional.main_functions import create_payment, get_payment
from app.models.main_models import Payment, PaymentStatus, WebhookLog
from app.services.webhooks.delivery import dispatch_webhook
from app.services.webhooks.retry import (
    can_manually_retry_webhook,
    claim_due_webhooks,
    compute_backoff_seconds,
    get_webhook_delivery_state,
)
from app.worker import process_due_webhooks_once


def test_backoff_and_delivery_state_helpers():
    assert compute_backoff_seconds(1) == 10
    assert compute_backoff_seconds(2) == 20
    assert compute_backoff_seconds(3) == 40
    assert compute_backoff_seconds(4) == 80

    p_new = Payment(
        id="p1",
        amount=1000,
        reference="R1",
        webhook_url="https://example.com/h",
        redirect_url="https://example.com/ok",
        status=PaymentStatus.PENDING.value,
    )
    assert get_webhook_delivery_state(p_new) == "never_attempted"
    assert can_manually_retry_webhook(p_new) is False

    p_sched = Payment(
        id="p2",
        amount=1000,
        reference="R2",
        webhook_url="https://example.com/h",
        redirect_url="https://example.com/ok",
        status=PaymentStatus.PAID.value,
        webhook_status="failed",
        webhook_attempts=2,
        webhook_next_attempt_at=utcnow() + timedelta(seconds=20),
    )
    assert get_webhook_delivery_state(p_sched) == "scheduled_retry"
    assert can_manually_retry_webhook(p_sched) is True

    p_exhausted = Payment(
        id="p3",
        amount=1000,
        reference="R3",
        webhook_url="https://example.com/h",
        redirect_url="https://example.com/ok",
        status=PaymentStatus.PAID.value,
        webhook_status="failed",
        webhook_attempts=5,
        webhook_next_attempt_at=None,
    )
    assert get_webhook_delivery_state(p_exhausted) == "exhausted"
    assert can_manually_retry_webhook(p_exhausted) is False


async def test_persisted_exponential_backoff_and_exhaustion(db_session, monkeypatch):
    payment = Payment(
        id="pay-backoff-1",
        amount=3500,
        reference="ORD-BACKOFF",
        webhook_url="https://merchant.example.com/hook",
        redirect_url="https://merchant.example.com/done",
        status=PaymentStatus.PAID.value,
        webhook_status="pending",
        webhook_next_attempt_at=utcnow(),
        card_mask="**** 4444",
    )
    await create_payment(db_session, payment)

    async def fake_getaddrinfo(self, host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]

    async def fake_post_fail(self, url, **kwargs):
        return httpx.Response(503, text="down" * 500)

    monkeypatch.setattr("asyncio.base_events.BaseEventLoop.getaddrinfo", fake_getaddrinfo)
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post_fail)

    for attempt in range(1, 6):
        db_session.expire_all()
        before = utcnow()
        ok = await dispatch_webhook("pay-backoff-1")
        assert ok is False

        db_session.expire_all()
        updated = await get_payment(db_session, "pay-backoff-1")
        assert updated.webhook_attempts == attempt
        assert updated.webhook_status == "failed"
        if attempt < 5:
            assert updated.webhook_next_attempt_at is not None
            delta = (updated.webhook_next_attempt_at - before).total_seconds()
            expected = compute_backoff_seconds(attempt)
            assert expected - 2 <= delta <= expected + 5
        else:
            assert updated.webhook_next_attempt_at is None
            assert get_webhook_delivery_state(updated) == "exhausted"

    logs = (
        await db_session.execute(select(WebhookLog).where(WebhookLog.payment_id == "pay-backoff-1"))
    ).scalars().all()
    assert len(logs) == 5
    assert all(len(log.response_body or "") <= 1000 for log in logs)


async def test_worker_does_not_redeliver_succeeded_and_claims_exclusively(tmp_path, monkeypatch):
    db_file = tmp_path / "worker_claim.db"
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{db_file}",
        connect_args={"check_same_thread": False},
    )
    session_factory = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    now = utcnow()
    async with session_factory() as session:
        session.add(
            Payment(
                id="pay-due-1",
                amount=1200,
                reference="ORD-DUE-1",
                webhook_url="https://merchant.example.com/hook",
                redirect_url="https://merchant.example.com/done",
                status=PaymentStatus.PAID.value,
                webhook_status="failed",
                webhook_attempts=1,
                webhook_next_attempt_at=now - timedelta(seconds=5),
                card_mask="**** 4444",
            )
        )
        session.add(
            Payment(
                id="pay-done-1",
                amount=1200,
                reference="ORD-DONE-1",
                webhook_url="https://merchant.example.com/hook",
                redirect_url="https://merchant.example.com/done",
                status=PaymentStatus.PAID.value,
                webhook_status="success",
                webhook_attempts=1,
                webhook_next_attempt_at=None,
                card_mask="**** 4444",
            )
        )
        await session.commit()

    async with session_factory() as s1, session_factory() as s2:
        claimed_1, claimed_2 = await asyncio.gather(
            claim_due_webhooks(s1),
            claim_due_webhooks(s2),
        )

    all_claimed = claimed_1 + claimed_2
    assert all_claimed == ["pay-due-1"]

    async with session_factory() as reset_s:
        p = await get_payment(reset_s, "pay-due-1")
        p.webhook_locked_until = None
        reset_s.add(p)
        await reset_s.commit()

    async def fake_getaddrinfo(self, host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]

    async def fake_post_ok(self, url, **kwargs):
        return httpx.Response(200, text="ok")

    monkeypatch.setattr("asyncio.base_events.BaseEventLoop.getaddrinfo", fake_getaddrinfo)
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post_ok)
    monkeypatch.setattr(db_session_module, "AsyncSessionLocal", session_factory)

    processed = await process_due_webhooks_once()
    assert processed == 1

    processed_again = await process_due_webhooks_once()
    assert processed_again == 0

    await engine.dispose()
