import os
from datetime import timedelta
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.time import utcnow
from app.models.errors import IdempotencyConflictError
from app.models.main_models import Payment, PaymentStatus
from app.services.payments.idempotency import (
    claim_idempotency_key,
    compute_payment_fingerprint,
)
from app.services.payments.lifecycle import finalize_successful_payment
from app.services.webhooks.retry import claim_due_webhooks

POSTGRES_TEST_URL = os.getenv("POSTGRES_TEST_URL")

pytestmark = pytest.mark.skipif(
    not POSTGRES_TEST_URL,
    reason="POSTGRES_TEST_URL is not set",
)


async def test_postgres_migrations_and_skip_locked(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", POSTGRES_TEST_URL)
    repo_root = Path(__file__).resolve().parents[1]
    cfg = Config(str(repo_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(repo_root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", POSTGRES_TEST_URL)
    command.upgrade(cfg, "head")

    engine = create_async_engine(POSTGRES_TEST_URL, echo=False)
    session_factory = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    async def fake_dispatch(payment_id: str, timeout: int = 10) -> bool:
        return True

    monkeypatch.setattr("app.services.webhook_service.dispatch_webhook", fake_dispatch)

    try:
        async with session_factory() as s:
            payment = Payment(
                id="pg-pay-1",
                amount=25000,
                reference="PG-ORD-1",
                webhook_url="https://merchant.example.com/hook",
                redirect_url="https://merchant.example.com/ok",
                status=PaymentStatus.WAITING_FOR_OTP.value,
                otp_email="pg@example.com",
                card_mask="**** 4444",
                expires_at=utcnow() + timedelta(minutes=10),
            )
            s.add(payment)
            await s.commit()

            fp = compute_payment_fingerprint("pg-pay-1", "pg@example.com", "4444444444444444", "12/30", None, None)
            await claim_idempotency_key(s, "pg-idem-1", "pg-pay-1", fp)
            with pytest.raises(IdempotencyConflictError):
                await claim_idempotency_key(s, "pg-idem-1", "pg-pay-other", fp)

            bg = BackgroundTasks()
            await finalize_successful_payment(payment, s, bg)

        async with session_factory() as s1, session_factory() as s2:
            c1 = await claim_due_webhooks(s1, batch_size=10)
            c2 = await claim_due_webhooks(s2, batch_size=10)
            assert "pg-pay-1" in c1
            assert "pg-pay-1" not in c2
    finally:
        await engine.dispose()
