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
    SavedCardNotFoundError
)
from app.models.main_models import Payment, SavedCard
from app.functional.main_functions import (
    create_payment,
    get_payment,
    update_payment,
    get_payment_by_idempotency
)
from app.security.sanitizer import clean_input
from app.security.crypto import (
    generate_csrf_token,
    generate_secure_otp,
    hash_sensitive_data,
    verify_sensitive_data
)
from app.services.smtp_service import send_otp_email
from app.core.config import BASE_URL, CURRENCY_SYMBOL
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
    from app.services.webhook_service import send_webhook_with_retry
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
            "reference": payment.reference,
            "card_mask": payment.card_mask,
            "currency_symbol": CURRENCY_SYMBOL
        })
        logger.info(f"Receipt email task added for {payment.otp_email}")

    background_tasks.add_task(send_webhook_with_retry, payment, db)


@router.post("/create-invoice", response_model=CreateInvoiceResponse)
async def create_invoice(invoice: CreateInvoiceRequest, db: AsyncSession = Depends(get_db)):
    clean_reference = clean_input(invoice.reference)
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
    if not cookie_token or cookie_token != csrf_token:
        logger.warning(f"CSRF Attack attempt on payment {payment_id}")
        raise CSRFTokenMismatchError(payment_id)

    if idempotency_key:
        existing = await get_payment_by_idempotency(db, idempotency_key)
        if existing and existing.id != payment_id:
            logger.info(f"Duplicate request detected with idempotency key {idempotency_key}")
            if existing.status == "paid":
                return RedirectResponse(url=f"/success/{existing.id}", status_code=303)
            elif existing.status == "waiting_for_otp":
                return RedirectResponse(url=f"/otp/{existing.id}", status_code=303)

    logger.info(f"Processing payment {payment_id} for email {email}")
    payment = await get_payment(db, payment_id)

    if not payment:
        raise PaymentNotFoundError(payment_id)

    if payment.status in ["paid", "expired", "failed"]:
        raise PaymentAlreadyProcessedError(payment_id)

    if idempotency_key:
        payment.idempotency_key = idempotency_key

    is_valid_card = False
    card_mask_display = ""
    save_card_bool = save_card == "true" if save_card else False

    if saved_card_id and saved_card_id.strip():
        card_id_int = int(saved_card_id)
        card_query = await db.execute(select(SavedCard).where(SavedCard.id == card_id_int))
        saved_card_obj = card_query.scalars().first()

        if not saved_card_obj:
            raise SavedCardNotFoundError(card_id_int)

        if verify_sensitive_data("4444444444444444", saved_card_obj.card_hash):
            is_valid_card = True
            card_mask_display = saved_card_obj.card_mask
            payment.otp_email = email
            payment.card_mask = saved_card_obj.card_mask

    elif card_number:
        card_number_clean = card_number.replace(" ", "")
        if card_number_clean == "4444444444444444":
            is_valid_card = True
            card_mask_display = f"**** {card_number_clean[-4:]}"
            payment.otp_email = email
            payment.card_mask = card_mask_display

            if save_card_bool:
                existing = await db.execute(select(SavedCard).where(
                    SavedCard.email == email,
                    SavedCard.card_mask == card_mask_display
                ))
                if not existing.scalars().first():
                    saved_card = SavedCard(
                        email=email,
                        card_token=str(uuid.uuid4()),
                        card_hash=hash_sensitive_data(card_number_clean),
                        cvv_hash=hash_sensitive_data(cvv),
                        expiry=expiry,
                        card_mask=card_mask_display,
                        psp_provider="mock"
                    )
                    db.add(saved_card)
                    await db.commit()
                    logger.info(f"Card saved for user {email}")

    if is_valid_card:
        cookie_email = request.cookies.get("user_email")
        if cookie_email and cookie_email == email:
            logger.info(f"Cookie matched for {email}, skipping OTP")
            await finalize_successful_payment(payment, db, background_tasks)
            response = RedirectResponse(url=f"/success/{payment_id}", status_code=303)
            response.set_cookie(
                key="user_email",
                value=email,
                max_age=2592000,
                httponly=True,
                secure=True,
                samesite="Strict"
            )
            return response

        otp_code = generate_secure_otp()
        payment.otp_code = otp_code
        payment.status = "waiting_for_otp"
        await update_payment(db, payment)

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