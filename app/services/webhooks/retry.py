from datetime import timedelta
from typing import Optional

from sqlalchemy import or_, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

import app.core.config as config
from app.core.time import utcnow
from app.models.main_models import Payment, PaymentStatus

_BASE_BACKOFF_SECONDS = 10


def compute_backoff_seconds(attempt_number: int) -> int:
    exponent = max(0, attempt_number - 1)
    return _BASE_BACKOFF_SECONDS * (2 ** exponent)


def compute_next_attempt_at(attempt_number: int) -> Optional[object]:
    if attempt_number >= config.WEBHOOK_MAX_ATTEMPTS:
        return None
    return utcnow() + timedelta(seconds=compute_backoff_seconds(attempt_number))


def get_webhook_delivery_state(payment: Payment) -> str:
    if payment.webhook_status == "success":
        return "succeeded"
    if payment.webhook_attempts >= config.WEBHOOK_MAX_ATTEMPTS:
        return "exhausted"
    if payment.webhook_status == "failed" and payment.webhook_next_attempt_at is not None:
        return "scheduled_retry"
    if payment.webhook_status == "failed":
        return "failed"
    if payment.webhook_status == "pending":
        return "pending"
    return "never_attempted"


def can_manually_retry_webhook(payment: Payment) -> bool:
    return (
        payment.status == PaymentStatus.PAID.value
        and payment.webhook_status != "success"
        and payment.webhook_attempts < config.WEBHOOK_MAX_ATTEMPTS
    )


async def claim_due_webhooks(
    session: AsyncSession,
    batch_size: int = 20,
    lease_seconds: int = 60,
) -> list[str]:
    now = utcnow()
    lease_until = now + timedelta(seconds=lease_seconds)

    bind = session.get_bind()
    dialect_name = bind.dialect.name if bind is not None else "sqlite"

    due_filter = (
        Payment.status == PaymentStatus.PAID.value,
        Payment.webhook_status.in_(["pending", "failed"]),
        Payment.webhook_attempts < config.WEBHOOK_MAX_ATTEMPTS,
        Payment.webhook_next_attempt_at.is_not(None),
        Payment.webhook_next_attempt_at <= now,
        or_(
            Payment.webhook_locked_until.is_(None),
            Payment.webhook_locked_until <= now,
        ),
    )

    if dialect_name == "postgresql":
        stmt = (
            select(Payment.id)
            .where(*due_filter)
            .order_by(Payment.webhook_next_attempt_at.asc())
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        )
        candidate_ids = list((await session.execute(stmt)).scalars().all())
        if not candidate_ids:
            await session.rollback()
            return []

        await session.execute(
            update(Payment)
            .where(Payment.id.in_(candidate_ids))
            .values(webhook_locked_until=lease_until, updated_at=now)
        )
        await session.commit()
        return candidate_ids

    candidate_stmt = (
        select(Payment.id)
        .where(*due_filter)
        .order_by(Payment.webhook_next_attempt_at.asc())
        .limit(batch_size)
    )
    candidate_ids = list((await session.execute(candidate_stmt)).scalars().all())
    if not candidate_ids:
        return []

    claimed_ids: list[str] = []
    for pid in candidate_ids:
        upd = (
            update(Payment)
            .where(
                Payment.id == pid,
                Payment.status == PaymentStatus.PAID.value,
                Payment.webhook_status.in_(["pending", "failed"]),
                Payment.webhook_attempts < config.WEBHOOK_MAX_ATTEMPTS,
                or_(
                    Payment.webhook_locked_until.is_(None),
                    Payment.webhook_locked_until <= now,
                ),
            )
            .values(webhook_locked_until=lease_until, updated_at=now)
        )
        result = await session.execute(upd)
        if int(result.rowcount or 0) == 1:
            claimed_ids.append(pid)

    await session.commit()
    return claimed_ids
