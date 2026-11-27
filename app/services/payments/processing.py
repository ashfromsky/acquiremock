import hmac
import logging
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional

from fastapi import BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.core.time import utcnow
from app.functional.main_functions import get_payment, update_payment
from app.models.errors import (
    InsufficientFundsError,
    InvalidCardError,
    PaymentAlreadyProcessedError,
    PaymentExpiredError,
    PaymentNotFoundError,
    SavedCardNotFoundError,
)
from app.models.main_models import PaymentStatus, SavedCard
from app.security.crypto import (
    generate_secure_otp,
    hash_sensitive_data,
    verify_sensitive_data,
)
from app.services.payments.idempotency import complete_idempotency_key
from app.services.payments.lifecycle import (
    expire_payment_if_needed,
    finalize_successful_payment,
)
import app.services.smtp_service as smtp_service

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PaymentSubmissionResult:
    redirect_url: str
    set_session_email: Optional[str] = None


async def process_payment_submission(
    db: AsyncSession,
    background_tasks: BackgroundTasks,
    payment_id: str,
    card_number: Optional[str],
    expiry: Optional[str],
    saved_card_id: Optional[str],
    email: str,
    save_card: Optional[str],
    verified_email: Optional[str],
    claimed_key: Optional[str],
) -> PaymentSubmissionResult:
    payment = await get_payment(db, payment_id)

    if not payment:
        raise PaymentNotFoundError(payment_id)

    if payment.status in [
        PaymentStatus.PAID.value,
        PaymentStatus.EXPIRED.value,
        PaymentStatus.FAILED.value,
    ]:
        raise PaymentAlreadyProcessedError(payment_id)

    if await expire_payment_if_needed(db, payment):
        raise PaymentExpiredError(payment_id)

    if claimed_key is not None and payment.idempotency_key is None:
        payment.idempotency_key = claimed_key

    is_valid_card = False
    save_card_bool = save_card == "true" if save_card else False

    if saved_card_id and saved_card_id.strip():
        try:
            card_id_int = int(saved_card_id.strip())
        except ValueError as exc:
            raise InvalidCardError(payment_id) from exc

        if not verified_email:
            raise SavedCardNotFoundError(card_id_int)

        card_query = await db.execute(
            select(SavedCard).where(
                SavedCard.id == card_id_int,
                SavedCard.email == verified_email,
            )
        )
        saved_card_obj = card_query.scalars().first()
        if not saved_card_obj:
            raise SavedCardNotFoundError(card_id_int)

        if verify_sensitive_data("4444444444444444", saved_card_obj.card_hash):
            is_valid_card = True
            payment.otp_email = verified_email
            payment.card_mask = saved_card_obj.card_mask

    elif card_number:
        card_number_clean = card_number.replace(" ", "")
        if card_number_clean == "4444444444444444":
            is_valid_card = True
            card_mask_display = f"**** {card_number_clean[-4:]}"
            payment.otp_email = email
            payment.card_mask = card_mask_display

            if save_card_bool:
                if not expiry or not expiry.strip():
                    raise InvalidCardError(payment_id)

                existing = await db.execute(
                    select(SavedCard).where(
                        SavedCard.email == email,
                        SavedCard.card_mask == card_mask_display,
                    )
                )
                if not existing.scalars().first():
                    saved_card = SavedCard(
                        email=email,
                        card_token=str(uuid.uuid4()),
                        card_hash=hash_sensitive_data(card_number_clean),
                        cvv_hash="",
                        expiry=expiry.strip(),
                        card_mask=card_mask_display,
                        psp_provider="mock",
                    )
                    db.add(saved_card)
                    await db.commit()
                    logger.info("Card saved for user %s", email)

    if is_valid_card:
        if verified_email and hmac.compare_digest(verified_email, email):
            logger.info("Signed session matched for %s, skipping OTP", email)
            await finalize_successful_payment(payment, db, background_tasks)
            target_url = f"/success/{payment_id}"
            if claimed_key is not None:
                await complete_idempotency_key(
                    db,
                    claimed_key,
                    response_status=303,
                    response_location=target_url,
                )
            return PaymentSubmissionResult(
                redirect_url=target_url,
                set_session_email=email,
            )

        otp_code = generate_secure_otp()
        now = utcnow()
        payment.otp_code = otp_code
        payment.otp_attempts = 0
        payment.otp_resend_count = 0
        payment.otp_expires_at = min(now + timedelta(minutes=5), payment.expires_at)
        payment.status = PaymentStatus.WAITING_FOR_OTP.value
        await update_payment(db, payment)

        target_url = f"/otp/{payment_id}"
        if claimed_key is not None:
            await complete_idempotency_key(
                db,
                claimed_key,
                response_status=303,
                response_location=target_url,
            )
        background_tasks.add_task(smtp_service.send_otp_email, email, otp_code)
        logger.info("OTP sent to %s", email)
        return PaymentSubmissionResult(redirect_url=target_url)

    logger.warning("Insufficient funds or invalid card for payment %s", payment_id)
    payment.status = PaymentStatus.FAILED.value
    payment.error_code = "INSUFFICIENT_FUNDS"
    payment.error_message = "Invalid card or insufficient funds"
    await update_payment(db, payment)
    raise InsufficientFundsError(payment_id)
