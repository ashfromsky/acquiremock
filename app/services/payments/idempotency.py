import hashlib
import json
from typing import Optional

from fastapi.responses import RedirectResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import delete, select

from app.core.time import utcnow
from app.models.errors import (
    IdempotencyConflictError,
    IdempotencyInProgressError,
    InsufficientFundsError,
    PaymentError,
    PaymentExpiredError,
)
from app.models.main_models import IdempotencyRecord

_MAX_IDEMPOTENCY_KEY_LENGTH = 128


def normalize_idempotency_key(
    raw_key: Optional[str],
    payment_id: Optional[str] = None,
) -> Optional[str]:
    if raw_key is None:
        return None
    cleaned = raw_key.strip()
    if not cleaned:
        raise IdempotencyConflictError(payment_id, "Idempotency-Key header cannot be empty")
    if len(cleaned) > _MAX_IDEMPOTENCY_KEY_LENGTH:
        raise IdempotencyConflictError(
            payment_id,
            f"Idempotency-Key must be {_MAX_IDEMPOTENCY_KEY_LENGTH} characters or fewer",
        )
    return cleaned


def compute_payment_fingerprint(
    payment_id: str,
    email: str,
    card_number: Optional[str],
    expiry: Optional[str],
    saved_card_id: Optional[str],
    save_card: Optional[str],
) -> str:
    card_normalized = (card_number or "").replace(" ", "").strip()
    payload = {
        "payment_id": payment_id,
        "email": email.strip().lower(),
        "card_sha256": hashlib.sha256(card_normalized.encode("utf-8")).hexdigest() if card_normalized else "",
        "expiry": (expiry or "").strip(),
        "saved_card_id": (saved_card_id or "").strip(),
        "save_card": (save_card or "").strip().lower(),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


async def claim_idempotency_key(
    db: AsyncSession,
    key: str,
    payment_id: str,
    fingerprint: str,
) -> Optional[IdempotencyRecord]:
    record = IdempotencyRecord(
        idempotency_key=key,
        payment_id=payment_id,
        request_fingerprint=fingerprint,
        status="in_progress",
        created_at=utcnow(),
        updated_at=utcnow(),
    )
    db.add(record)
    try:
        await db.commit()
        return None
    except IntegrityError:
        await db.rollback()

    existing = (
        await db.execute(
            select(IdempotencyRecord).where(IdempotencyRecord.idempotency_key == key)
        )
    ).scalars().first()
    if not existing:
        raise IdempotencyInProgressError(payment_id)

    if existing.payment_id != payment_id:
        raise IdempotencyConflictError(
            payment_id,
            "Idempotency-Key was already used for a different payment",
        )
    if existing.request_fingerprint != fingerprint:
        raise IdempotencyConflictError(
            payment_id,
            "Idempotency-Key was reused with incompatible request parameters",
        )
    if existing.status == "in_progress":
        raise IdempotencyInProgressError(payment_id)

    return existing


async def complete_idempotency_key(
    db: AsyncSession,
    key: str,
    response_status: int,
    response_location: Optional[str] = None,
    error_code: Optional[str] = None,
    error_message: Optional[str] = None,
) -> None:
    record = (
        await db.execute(
            select(IdempotencyRecord).where(IdempotencyRecord.idempotency_key == key)
        )
    ).scalars().first()
    if not record:
        return
    record.status = "completed"
    record.response_status = response_status
    record.response_location = response_location
    record.error_code = error_code
    record.error_message = error_message
    record.updated_at = utcnow()
    db.add(record)
    await db.commit()


async def release_idempotency_key(db: AsyncSession, key: str) -> None:
    await db.rollback()
    await db.execute(
        delete(IdempotencyRecord).where(
            IdempotencyRecord.idempotency_key == key,
            IdempotencyRecord.status == "in_progress",
        )
    )
    await db.commit()


def replay_idempotency_outcome(record: IdempotencyRecord) -> RedirectResponse:
    if record.response_status == 303 and record.response_location:
        return RedirectResponse(url=record.response_location, status_code=303)
    if record.error_code == "INSUFFICIENT_FUNDS":
        raise InsufficientFundsError(record.payment_id)
    if record.error_code == "PAYMENT_EXPIRED":
        raise PaymentExpiredError(record.payment_id)
    raise PaymentError(
        code=record.error_code or "PAYMENT_ERROR",
        message=record.error_message or "Payment request failed",
        status_code=record.response_status or 409,
        payment_id=record.payment_id,
    )
