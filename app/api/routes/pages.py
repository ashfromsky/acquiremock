import hmac
import logging
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import COOKIE_SECURE, CURRENCY_SYMBOL
from app.core.limiter import limiter
from app.database.core.session import get_db
from app.functional.main_functions import get_payment, update_payment
from app.models.errors import (
    CSRFTokenMismatchError,
    InvalidOTPError,
    PaymentAlreadyProcessedError,
    PaymentError,
    PaymentExpiredError,
    PaymentNotFoundError,
)
from app.models.main_models import PaymentStatus
from app.security.crypto import (
    create_signed_email_token,
    generate_csrf_token,
    generate_secure_otp,
)
from app.services.smtp_service import send_otp_email

logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory="templates/pages")

router = APIRouter(
    tags=["pages"],
)


@router.get("/otp/{payment_id}", response_class=HTMLResponse)
async def otp_page(payment_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    payment = await get_payment(db, payment_id)

    if not payment:
        raise PaymentNotFoundError(payment_id)

    if payment.expires_at < datetime.utcnow():
        payment.status = PaymentStatus.EXPIRED
        await update_payment(db, payment)
        raise PaymentExpiredError(payment_id)

    if payment.status != PaymentStatus.WAITING_FOR_OTP:
        if payment.status in [PaymentStatus.PAID, PaymentStatus.FAILED, PaymentStatus.EXPIRED]:
            raise PaymentAlreadyProcessedError(payment_id)
        raise PaymentNotFoundError(payment_id)

    csrf_token = generate_csrf_token()
    response = templates.TemplateResponse(request, "otp-page.html", {
        "request": request,
        "payment_id": payment_id,
        "email": payment.otp_email,
        "csrf_token": csrf_token,
    })
    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="Strict",
    )
    return response


@router.post("/otp/verify/{payment_id}")
@limiter.limit("5/minute")
async def verify_otp(
        request: Request,
        payment_id: str,
        background_tasks: BackgroundTasks,
        otp_code: str = Form(...),
        csrf_token: str = Form(...),
        db: AsyncSession = Depends(get_db)
):
    from app.api.routes.payments import finalize_successful_payment

    cookie_token = request.cookies.get("csrf_token")
    if not cookie_token or not hmac.compare_digest(cookie_token, csrf_token):
        raise CSRFTokenMismatchError(payment_id)

    logger.info(f"Verifying OTP for {payment_id}")
    payment = await get_payment(db, payment_id)

    if not payment:
        raise PaymentNotFoundError(payment_id)

    if payment.status in [PaymentStatus.PAID, PaymentStatus.FAILED, PaymentStatus.EXPIRED]:
        raise PaymentAlreadyProcessedError(payment_id)

    if payment.status != PaymentStatus.WAITING_FOR_OTP:
        raise PaymentError("INVALID_PAYMENT_STATE", "Payment is not awaiting OTP", 409, payment_id)

    if payment.expires_at < datetime.utcnow():
        payment.status = PaymentStatus.EXPIRED
        await update_payment(db, payment)
        raise PaymentExpiredError(payment_id)

    if not payment.otp_code or not hmac.compare_digest(payment.otp_code, otp_code):
        logger.warning(f"Invalid OTP for {payment_id}")
        raise InvalidOTPError(payment_id)

    payment.otp_code = None
    await finalize_successful_payment(payment, db, background_tasks)

    response = RedirectResponse(url=f"/success/{payment_id}", status_code=303)
    if payment.otp_email:
        response.set_cookie(
            key="user_session",
            value=create_signed_email_token(payment.otp_email),
            max_age=2592000,
            httponly=True,
            secure=COOKIE_SECURE,
            samesite="lax"
        )
    return response


@router.post("/otp/resend/{payment_id}")
@limiter.limit("3/minute")
async def resend_otp(
        request: Request,
        payment_id: str,
        background_tasks: BackgroundTasks,
        csrf_token: str = Form(...),
        db: AsyncSession = Depends(get_db)
):
    cookie_token = request.cookies.get("csrf_token")
    if not cookie_token or not hmac.compare_digest(cookie_token, csrf_token):
        raise CSRFTokenMismatchError(payment_id)

    payment = await get_payment(db, payment_id)
    if not payment:
        raise PaymentNotFoundError(payment_id)

    if payment.status in [PaymentStatus.PAID, PaymentStatus.FAILED, PaymentStatus.EXPIRED]:
        raise PaymentAlreadyProcessedError(payment_id)

    if payment.status != PaymentStatus.WAITING_FOR_OTP:
        raise PaymentError("INVALID_PAYMENT_STATE", "Payment is not awaiting OTP", 409, payment_id)

    if payment.expires_at < datetime.utcnow():
        payment.status = PaymentStatus.EXPIRED
        await update_payment(db, payment)
        raise PaymentExpiredError(payment_id)

    otp_code = generate_secure_otp()
    payment.otp_code = otp_code
    await update_payment(db, payment)

    if payment.otp_email:
        background_tasks.add_task(send_otp_email, payment.otp_email, otp_code)

    return RedirectResponse(url=f"/otp/{payment_id}", status_code=303)


@router.get("/success/{payment_id}", response_class=HTMLResponse)
async def payment_success(payment_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    payment = await get_payment(db, payment_id)

    if not payment:
        raise PaymentNotFoundError(payment_id)

    return templates.TemplateResponse(request, "success-page.html", {
        "request": request,
        "payment_id": payment.id,
        "amount": payment.amount,
        "reference": payment.reference,
        "card_mask": payment.card_mask,
        "redirect_url": payment.redirect_url,
        "currency_symbol": CURRENCY_SYMBOL
    })
