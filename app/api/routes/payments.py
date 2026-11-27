import hmac
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, Form, Header, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import BASE_URL, COOKIE_SECURE, CUSTOMER_SESSION_TTL_SECONDS
from app.core.limiter import limiter
from app.database.core.session import get_db
from app.models.errors import (
    CSRFTokenMismatchError,
    InsufficientFundsError,
    PaymentExpiredError,
)
from app.models.invoice import CreateInvoiceRequest, CreateInvoiceResponse
from app.security.crypto import create_signed_email_token, verify_signed_email_token
from app.services.payments.creation import create_invoice_payment
from app.services.payments.idempotency import (
    claim_idempotency_key,
    complete_idempotency_key,
    compute_payment_fingerprint,
    normalize_idempotency_key,
    release_idempotency_key,
    replay_idempotency_outcome,
)
from app.services.payments.lifecycle import finalize_successful_payment
from app.services.payments.processing import process_payment_submission

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api",
    tags=["payments"],
)


@router.post("/create-invoice", response_model=CreateInvoiceResponse)
@limiter.limit("30/minute")
async def create_invoice(
    request: Request,
    invoice: CreateInvoiceRequest,
    db: AsyncSession = Depends(get_db),
):
    payment = await create_invoice_payment(db, invoice)
    page_url = f"{BASE_URL}/checkout/{payment.id}"
    logger.info("Invoice created: %s", payment.id)
    return CreateInvoiceResponse(pageUrl=page_url)


@router.post("/pay/{payment_id}")
@limiter.limit("5/minute")
async def process_payment(
    request: Request,
    payment_id: str,
    background_tasks: BackgroundTasks,
    card_number: Optional[str] = Form(None),
    expiry: Optional[str] = Form(None),
    cvv: Optional[str] = Form(None),
    saved_card_id: Optional[str] = Form(None),
    email: str = Form(...),
    save_card: Optional[str] = Form(None),
    csrf_token: str = Form(...),
    idempotency_key: Optional[str] = Header(None),
    db: AsyncSession = Depends(get_db),
):
    cookie_token = request.cookies.get("csrf_token")
    if not cookie_token or not hmac.compare_digest(cookie_token, csrf_token):
        logger.warning("CSRF Attack attempt on payment %s", payment_id)
        raise CSRFTokenMismatchError(payment_id)

    claimed_key = normalize_idempotency_key(idempotency_key, payment_id)
    if claimed_key is not None:
        fingerprint = compute_payment_fingerprint(
            payment_id=payment_id,
            email=email,
            card_number=card_number,
            expiry=expiry,
            saved_card_id=saved_card_id,
            save_card=save_card,
        )
        existing_record = await claim_idempotency_key(
            db,
            claimed_key,
            payment_id,
            fingerprint,
        )
        if existing_record is not None:
            logger.info("Replaying idempotent outcome for payment %s", payment_id)
            return replay_idempotency_outcome(existing_record)

    verified_email = verify_signed_email_token(request.cookies.get("user_session"))

    try:
        result = await process_payment_submission(
            db=db,
            background_tasks=background_tasks,
            payment_id=payment_id,
            card_number=card_number,
            expiry=expiry,
            saved_card_id=saved_card_id,
            email=email,
            save_card=save_card,
            verified_email=verified_email,
            claimed_key=claimed_key,
        )
    except (InsufficientFundsError, PaymentExpiredError) as exc:
        if claimed_key is not None:
            await complete_idempotency_key(
                db,
                claimed_key,
                response_status=exc.status_code,
                error_code=exc.code,
                error_message=exc.message,
            )
        raise
    except Exception:
        if claimed_key is not None:
            await release_idempotency_key(db, claimed_key)
        raise

    response = RedirectResponse(url=result.redirect_url, status_code=303)
    if result.set_session_email:
        response.set_cookie(
            key="user_session",
            value=create_signed_email_token(result.set_session_email),
            max_age=CUSTOMER_SESSION_TTL_SECONDS,
            httponly=True,
            secure=COOKIE_SECURE,
            samesite="lax",
            path="/",
        )
    return response


__all__ = ["finalize_successful_payment", "router"]
