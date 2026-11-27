import hmac
import uuid
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Request, Form, BackgroundTasks, Header
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app.database.core.session import get_db
from app.models.invoice import CreateInvoiceRequest, CreateInvoiceResponse
from app.models.errors import (
    PaymentNotFoundError,
    PaymentAlreadyProcessedError,
    PaymentExpiredError,
    CSRFTokenMismatchError,
    InsufficientFundsError,
    InvalidCardError,
    SavedCardNotFoundError
)
from app.models.main_models import Payment, PaymentStatus, SavedCard
from app.functional.main_functions import (
    create_payment,
    get_payment,
    update_payment,
)
from app.services.payments.idempotency import (
    claim_idempotency_key,
    complete_idempotency_key,
    compute_payment_fingerprint,
    normalize_idempotency_key,
    release_idempotency_key,
    replay_idempotency_outcome,
)
from app.security.sanitizer import validate_reference
from app.security.crypto import (
    create_signed_email_token,
    generate_csrf_token,
    generate_secure_otp,
    hash_sensitive_data,
    verify_sensitive_data,
    verify_signed_email_token
)
from app.services.smtp_service import send_otp_email
from app.core.config import BASE_URL, COOKIE_SECURE, CURRENCY_CODE, CURRENCY_SYMBOL
from app.core.currency import format_minor_amount
from app.core.limiter import limiter

logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory="templates/pages")

router = APIRouter(
    prefix="/api",
    tags=["payments"],
)


async def finalize_successful_payment(
        payment: Payment,
        db: AsyncSession,
        background_tasks: BackgroundTasks
):
    from app.models.main_models import SuccessfulOperation
    from app.functional.main_functions import send_successful_operation
    from app.services.webhook_service import dispatch_webhook
    from app.services.smtp_service import send_receipt_email

    logger.info(f"Finalizing payment {payment.id}")
    payment.status = "paid"
    payment.paid_at = datetime.utcnow()
    await update_payment(db, payment)

    try:
        new_op = SuccessfulOperation(
            payment_id=payment.id,
            email=payment.otp_email,
            amount=payment.amount,
            reference=payment.reference,
            card_mask=payment.card_mask,
            redirect_url=payment.redirect_url
        )
        await send_successful_operation(db, new_op)
        logger.info(f"Operation {payment.id} saved to DB")
    except Exception as e:
        logger.error(f"DB Error during finalization: {e}")

    if payment.otp_email:
        background_tasks.add_task(send_receipt_email, payment.otp_email, {
            "payment_id": payment.id,
            "amount": payment.amount,
            "formatted_amount": format_minor_amount(payment.amount, CURRENCY_CODE, CURRENCY_SYMBOL),
            "reference": payment.reference,
            "card_mask": payment.card_mask,
            "currency_code": CURRENCY_CODE,
            "currency_symbol": CURRENCY_SYMBOL
        })
        logger.info(f"Receipt email task added for {payment.otp_email}")

    background_tasks.add_task(dispatch_webhook, payment.id)


@router.post("/create-invoice", response_model=CreateInvoiceResponse)
@limiter.limit("30/minute")
async def create_invoice(
        request: Request,
        invoice: CreateInvoiceRequest,
        db: AsyncSession = Depends(get_db)
):
    clean_reference = validate_reference(invoice.reference)
    logger.info(f"Creating invoice for amount {invoice.amount}, ref {clean_reference}")
    payment_id = str(uuid.uuid4())

    payment = Payment(
        id=payment_id,
        amount=invoice.amount,
        reference=clean_reference,
        webhook_url=invoice.webhook_url,
        redirect_url=invoice.redirect_url,
        status="pending",
        expires_at=datetime.utcnow() + timedelta(minutes=15)
    )

    await create_payment(db, payment)
    page_url = f"{BASE_URL}/checkout/{payment_id}"
    logger.info(f"Invoice created: {payment_id}")
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
        db: AsyncSession = Depends(get_db)
):
    cookie_token = request.cookies.get("csrf_token")
    if not cookie_token or not hmac.compare_digest(cookie_token, csrf_token):
        logger.warning(f"CSRF Attack attempt on payment {payment_id}")
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

    try:
        return await _execute_payment_submission(
            request=request,
            payment_id=payment_id,
            background_tasks=background_tasks,
            card_number=card_number,
            expiry=expiry,
            cvv=cvv,
            saved_card_id=saved_card_id,
            email=email,
            save_card=save_card,
            claimed_key=claimed_key,
            db=db,
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


async def _execute_payment_submission(
    request: Request,
    payment_id: str,
    background_tasks: BackgroundTasks,
    card_number: Optional[str],
    expiry: Optional[str],
    cvv: Optional[str],
    saved_card_id: Optional[str],
    email: str,
    save_card: Optional[str],
    claimed_key: Optional[str],
    db: AsyncSession,
):
    logger.info(f"Processing payment {payment_id} for email {email}")
    payment = await get_payment(db, payment_id)

    if not payment:
        raise PaymentNotFoundError(payment_id)

    if payment.status in [PaymentStatus.PAID, PaymentStatus.EXPIRED, PaymentStatus.FAILED]:
        raise PaymentAlreadyProcessedError(payment_id)

    if payment.expires_at < datetime.utcnow():
        payment.status = PaymentStatus.EXPIRED
        await update_payment(db, payment)
        raise PaymentExpiredError(payment_id)

    if claimed_key is not None and payment.idempotency_key is None:
        payment.idempotency_key = claimed_key

    is_valid_card = False
    card_mask_display = ""
    save_card_bool = save_card == "true" if save_card else False

    verified_email = verify_signed_email_token(request.cookies.get("user_session"))

    if saved_card_id and saved_card_id.strip():
        try:
            card_id_int = int(saved_card_id.strip())
        except ValueError:
            raise InvalidCardError(payment_id)

        if not verified_email:
            raise SavedCardNotFoundError(card_id_int)

        card_query = await db.execute(
            select(SavedCard).where(
                SavedCard.id == card_id_int,
                SavedCard.email == verified_email
            )
        )
        saved_card_obj = card_query.scalars().first()

        if not saved_card_obj:
            raise SavedCardNotFoundError(card_id_int)

        if verify_sensitive_data("4444444444444444", saved_card_obj.card_hash):
            is_valid_card = True
            card_mask_display = saved_card_obj.card_mask
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

                existing = await db.execute(select(SavedCard).where(
                    SavedCard.email == email,
                    SavedCard.card_mask == card_mask_display
                ))
                if not existing.scalars().first():
                    saved_card = SavedCard(
                        email=email,
                        card_token=str(uuid.uuid4()),
                        card_hash=hash_sensitive_data(card_number_clean),
                        cvv_hash="",
                        expiry=expiry.strip(),
                        card_mask=card_mask_display,
                        psp_provider="mock"
                    )
                    db.add(saved_card)
                    await db.commit()
                    logger.info(f"Card saved for user {email}")

    if is_valid_card:
        if verified_email and hmac.compare_digest(verified_email, email):
            logger.info(f"Signed session matched for {email}, skipping OTP")
            await finalize_successful_payment(payment, db, background_tasks)
            target_url = f"/success/{payment_id}"
            if claimed_key is not None:
                await complete_idempotency_key(
                    db,
                    claimed_key,
                    response_status=303,
                    response_location=target_url,
                )
            response = RedirectResponse(url=target_url, status_code=303)
            response.set_cookie(
                key="user_session",
                value=create_signed_email_token(email),
                max_age=2592000,
                httponly=True,
                secure=COOKIE_SECURE,
                samesite="lax"
            )
            return response

        otp_code = generate_secure_otp()
        payment.otp_code = otp_code
        payment.status = "waiting_for_otp"
        await update_payment(db, payment)

        if claimed_key is not None:
            await complete_idempotency_key(
                db,
                claimed_key,
                response_status=303,
                response_location=f"/otp/{payment_id}",
            )
        background_tasks.add_task(send_otp_email, email, otp_code)
        logger.info(f"OTP sent to {email}")
        return RedirectResponse(url=f"/otp/{payment_id}", status_code=303)
    else:
        logger.warning(f"Insufficient funds or invalid card for payment {payment_id}")
        payment.status = "failed"
        payment.error_code = "INSUFFICIENT_FUNDS"
        payment.error_message = "Invalid card or insufficient funds"
        await update_payment(db, payment)
        raise InsufficientFundsError(payment_id)