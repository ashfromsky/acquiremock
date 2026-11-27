import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.config import (
    ALLOW_LOCAL_WEBHOOKS,
    BASE_URL,
    CURRENCY_CODE,
    CURRENCY_SYMBOL,
)
from app.core.limiter import limiter
from app.database.core.session import get_db
from app.functional.main_functions import get_payment
from app.models.errors import PaymentNotFoundError
from app.models.main_models import Payment, PaymentStatus, WebhookLog
from app.services.smtp_service import EMAIL_ENABLED
from app.services.webhook_service import send_webhook_with_retry

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/console",
    tags=["console"],
)


def _serialize_payment(payment: Payment) -> dict:
    return {
        "id": payment.id,
        "amount": payment.amount,
        "reference": payment.reference,
        "status": payment.status,
        "card_mask": payment.card_mask,
        "webhook_url": payment.webhook_url,
        "redirect_url": payment.redirect_url,
        "webhook_status": payment.webhook_status,
        "webhook_attempts": payment.webhook_attempts,
        "webhook_last_attempt": (
            payment.webhook_last_attempt.isoformat()
            if payment.webhook_last_attempt
            else None
        ),
        "error_code": payment.error_code,
        "error_message": payment.error_message,
        "created_at": payment.created_at.isoformat(),
        "updated_at": payment.updated_at.isoformat(),
        "expires_at": payment.expires_at.isoformat(),
        "paid_at": payment.paid_at.isoformat() if payment.paid_at else None,
    }


def _serialize_webhook_log(log: WebhookLog) -> dict:
    return {
        "id": log.id,
        "payment_id": log.payment_id,
        "webhook_url": log.webhook_url,
        "payload": log.payload,
        "response_status": log.response_status,
        "response_body": log.response_body,
        "signature": log.signature,
        "attempt_number": log.attempt_number,
        "success": log.success,
        "error_message": log.error_message,
        "created_at": log.created_at.isoformat(),
    }


@router.get("/config")
async def get_console_config():
    return {
        "version": "2.0.0",
        "base_url": BASE_URL,
        "currency_code": CURRENCY_CODE,
        "currency_symbol": CURRENCY_SYMBOL,
        "smtp_enabled": EMAIL_ENABLED,
        "allow_local_webhooks": ALLOW_LOCAL_WEBHOOKS,
        "payment_ttl_minutes": 15,
        "max_webhook_attempts": 5,
    }


@router.get("/overview")
async def get_console_overview(db: AsyncSession = Depends(get_db)):
    status_rows = (
        await db.execute(
            select(Payment.status, func.count(Payment.id), func.coalesce(func.sum(Payment.amount), 0))
            .group_by(Payment.status)
        )
    ).all()

    counts = {
        PaymentStatus.PAID.value: 0,
        PaymentStatus.PENDING.value: 0,
        PaymentStatus.WAITING_FOR_OTP.value: 0,
        PaymentStatus.FAILED.value: 0,
        PaymentStatus.EXPIRED.value: 0,
        PaymentStatus.REFUNDED.value: 0,
    }
    paid_volume = 0.0
    total_payments = 0

    for status_value, count, amount_sum in status_rows:
        key = str(status_value)
        total_payments += int(count)
        if key in counts:
            counts[key] = int(count)
        if key == PaymentStatus.PAID.value:
            paid_volume = float(amount_sum or 0)

    webhook_rows = (
        await db.execute(
            select(WebhookLog.success, func.count(WebhookLog.id)).group_by(WebhookLog.success)
        )
    ).all()

    succeeded_webhooks = 0
    failed_webhooks = 0
    for is_success, count in webhook_rows:
        if is_success:
            succeeded_webhooks += int(count)
        else:
            failed_webhooks += int(count)

    total_webhooks = succeeded_webhooks + failed_webhooks
    success_rate = (
        round((succeeded_webhooks / total_webhooks) * 100, 1)
        if total_webhooks > 0
        else None
    )

    recent_result = await db.execute(
        select(Payment).order_by(Payment.created_at.desc()).limit(8)
    )
    recent_payments = [_serialize_payment(p) for p in recent_result.scalars().all()]

    return {
        "payments": {
            "total": total_payments,
            "paid": counts[PaymentStatus.PAID.value],
            "pending": counts[PaymentStatus.PENDING.value],
            "waiting_for_otp": counts[PaymentStatus.WAITING_FOR_OTP.value],
            "failed": counts[PaymentStatus.FAILED.value],
            "expired": counts[PaymentStatus.EXPIRED.value],
            "paid_volume": paid_volume,
        },
        "webhooks": {
            "total": total_webhooks,
            "succeeded": succeeded_webhooks,
            "failed": failed_webhooks,
            "success_rate": success_rate,
        },
        "recent_payments": recent_payments,
    }


@router.get("/payments")
async def list_console_payments(
    status: Optional[str] = Query(None),
    q: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    filters = []
    if status and status != "all":
        filters.append(Payment.status == status)
    if q and q.strip():
        term = f"%{q.strip()}%"
        filters.append(or_(Payment.reference.ilike(term), Payment.id.ilike(term)))

    count_stmt = select(func.count(Payment.id))
    list_stmt = select(Payment)
    for condition in filters:
        count_stmt = count_stmt.where(condition)
        list_stmt = list_stmt.where(condition)

    total = int((await db.execute(count_stmt)).scalar() or 0)
    rows = (
        await db.execute(
            list_stmt.order_by(Payment.created_at.desc()).offset(offset).limit(limit)
        )
    ).scalars().all()

    return {
        "items": [_serialize_payment(p) for p in rows],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/payments/{payment_id}")
async def get_console_payment_detail(
    payment_id: str,
    db: AsyncSession = Depends(get_db),
):
    payment = await get_payment(db, payment_id)
    if not payment:
        raise PaymentNotFoundError(payment_id)

    logs = (
        await db.execute(
            select(WebhookLog)
            .where(WebhookLog.payment_id == payment_id)
            .order_by(WebhookLog.created_at.desc(), WebhookLog.id.desc())
        )
    ).scalars().all()

    data = _serialize_payment(payment)
    data["webhook_logs"] = [_serialize_webhook_log(log) for log in logs]
    return data


@router.get("/webhooks")
async def list_console_webhooks(
    success: Optional[bool] = Query(None),
    payment_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    filters = []
    if success is not None:
        filters.append(WebhookLog.success == success)
    if payment_id and payment_id.strip():
        filters.append(WebhookLog.payment_id.ilike(f"%{payment_id.strip()}%"))

    count_stmt = select(func.count(WebhookLog.id))
    list_stmt = select(WebhookLog)
    for condition in filters:
        count_stmt = count_stmt.where(condition)
        list_stmt = list_stmt.where(condition)

    total = int((await db.execute(count_stmt)).scalar() or 0)
    logs = (
        await db.execute(
            list_stmt.order_by(WebhookLog.created_at.desc(), WebhookLog.id.desc())
            .offset(offset)
            .limit(limit)
        )
    ).scalars().all()

    summary_rows = (
        await db.execute(
            select(WebhookLog.success, func.count(WebhookLog.id)).group_by(WebhookLog.success)
        )
    ).all()
    succeeded = 0
    failed = 0
    for is_ok, cnt in summary_rows:
        if is_ok:
            succeeded += int(cnt)
        else:
            failed += int(cnt)

    return {
        "items": [_serialize_webhook_log(log) for log in logs],
        "total": total,
        "summary": {
            "total": succeeded + failed,
            "succeeded": succeeded,
            "failed": failed,
        },
    }


@router.post("/webhooks/{payment_id}/retry")
@limiter.limit("10/minute")
async def retry_console_webhook(
    request: Request,
    payment_id: str,
    db: AsyncSession = Depends(get_db),
):
    payment = await get_payment(db, payment_id)
    if not payment:
        raise PaymentNotFoundError(payment_id)

    success = await send_webhook_with_retry(payment, db)

    latest_log = (
        await db.execute(
            select(WebhookLog)
            .where(WebhookLog.payment_id == payment_id)
            .order_by(WebhookLog.id.desc())
            .limit(1)
        )
    ).scalars().first()

    return {
        "success": success,
        "payment_id": payment.id,
        "webhook_status": payment.webhook_status,
        "webhook_attempts": payment.webhook_attempts,
        "latest_log": _serialize_webhook_log(latest_log) if latest_log else None,
    }
