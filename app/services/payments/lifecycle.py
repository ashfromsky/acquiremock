import logging

from fastapi import BackgroundTasks
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

import app.core.config as config
import app.services.smtp_service as smtp_service
import app.services.webhook_service as webhook_service
from app.core.currency import format_minor_amount
from app.core.time import utcnow
from app.functional.main_functions import get_payment
from app.models.errors import (
    PaymentAlreadyProcessedError,
    PaymentError,
    PaymentExpiredError,
)
from app.models.main_models import Payment, PaymentStatus, SuccessfulOperation

logger = logging.getLogger(__name__)

ALLOWED_FINALIZATION_STATUSES = (
    PaymentStatus.PENDING.value,
    PaymentStatus.WAITING_FOR_OTP.value,
)
EXPIRABLE_PAYMENT_STATUSES = (
    PaymentStatus.PENDING.value,
    PaymentStatus.WAITING_FOR_OTP.value,
)


async def expire_payment_if_needed(db: AsyncSession, payment: Payment) -> bool:
    now = utcnow()
    if payment.status not in EXPIRABLE_PAYMENT_STATUSES or payment.expires_at > now:
        return False

    stmt = (
        update(Payment)
        .where(
            Payment.id == payment.id,
            Payment.status.in_(EXPIRABLE_PAYMENT_STATUSES),
            Payment.expires_at <= now,
        )
        .values(
            status=PaymentStatus.EXPIRED.value,
            otp_code=None,
            otp_expires_at=None,
            updated_at=now,
        )
    )
    result = await db.execute(stmt)
    await db.commit()
    await db.refresh(payment)
    return int(result.rowcount or 0) > 0


async def expire_overdue_payments(db: AsyncSession) -> int:
    now = utcnow()
    stmt = (
        update(Payment)
        .where(
            Payment.status.in_(EXPIRABLE_PAYMENT_STATUSES),
            Payment.expires_at <= now,
        )
        .values(
            status=PaymentStatus.EXPIRED.value,
            otp_code=None,
            otp_expires_at=None,
            updated_at=now,
        )
    )
    result = await db.execute(stmt)
    await db.commit()
    return int(result.rowcount or 0)


async def finalize_successful_payment(
    payment: Payment,
    db: AsyncSession,
    background_tasks: BackgroundTasks,
) -> Payment:
    now = utcnow()
    payment_id = payment.id
    payment_status = payment.status
    payment_expires_at = payment.expires_at
    otp_email = payment.otp_email
    amount = payment.amount
    reference = payment.reference
    card_mask = payment.card_mask
    redirect_url = payment.redirect_url
    idempotency_key = payment.idempotency_key

    if payment_status not in ALLOWED_FINALIZATION_STATUSES:
        if payment_status in (
            PaymentStatus.PAID.value,
            PaymentStatus.FAILED.value,
            PaymentStatus.EXPIRED.value,
        ):
            raise PaymentAlreadyProcessedError(payment_id)
        raise PaymentError(
            "INVALID_PAYMENT_STATE",
            "Payment cannot be finalized in its current state",
            409,
            payment_id,
        )

    if payment_expires_at <= now:
        await expire_payment_if_needed(db, payment)
        raise PaymentExpiredError(payment_id)

    try:
        stmt = (
            update(Payment)
            .where(
                Payment.id == payment_id,
                Payment.status.in_(ALLOWED_FINALIZATION_STATUSES),
                Payment.expires_at > now,
            )
            .values(
                status=PaymentStatus.PAID.value,
                paid_at=now,
                updated_at=now,
                otp_code=None,
                otp_expires_at=None,
                otp_email=otp_email,
                card_mask=card_mask,
                idempotency_key=idempotency_key,
                webhook_status="pending",
                webhook_next_attempt_at=now,
            )
        )
        result = await db.execute(stmt)
        if int(result.rowcount or 0) != 1:
            await db.rollback()
            latest = await get_payment(db, payment_id)
            if latest and latest.status in EXPIRABLE_PAYMENT_STATUSES and latest.expires_at <= now:
                await expire_payment_if_needed(db, latest)
                raise PaymentExpiredError(payment_id)
            raise PaymentAlreadyProcessedError(payment_id)

        operation = SuccessfulOperation(
            payment_id=payment_id,
            email=otp_email or "",
            amount=amount,
            reference=reference,
            card_mask=card_mask or "",
            redirect_url=redirect_url,
            created_at=now,
        )
        db.add(operation)
        await db.commit()
    except (PaymentAlreadyProcessedError, PaymentExpiredError, PaymentError):
        raise
    except Exception as exc:
        await db.rollback()
        logger.error("Atomic finalization failed for payment %s: %s", payment_id, exc)
        raise

    await db.refresh(payment)

    if payment.otp_email:
        background_tasks.add_task(
            smtp_service.send_receipt_email,
            payment.otp_email,
            {
                "payment_id": payment.id,
                "amount": payment.amount,
                "formatted_amount": format_minor_amount(
                    payment.amount,
                    config.CURRENCY_CODE,
                    config.CURRENCY_SYMBOL,
                ),
                "reference": payment.reference,
                "card_mask": payment.card_mask,
                "currency_code": config.CURRENCY_CODE,
                "currency_symbol": config.CURRENCY_SYMBOL,
            },
        )
        logger.info("Receipt email task added for %s", payment.otp_email)

    background_tasks.add_task(webhook_service.dispatch_webhook, payment.id)
    return payment
