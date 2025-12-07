import logging
from fastapi import APIRouter, Request, Form, Depends, BackgroundTasks
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.database.core.session import get_db
from app.functional.main_functions import get_payment, update_payment
from app.models.errors import PaymentNotFoundError, InvalidOTPError
from app.core.config import CURRENCY_SYMBOL

logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory="templates/pages")

router = APIRouter(
    tags=["pages"],
)


@router.get("/otp/{payment_id}", response_class=HTMLResponse)
async def otp_page(payment_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    payment = await get_payment(db, payment_id)

    if not payment or payment.status != "waiting_for_otp":
        raise PaymentNotFoundError(payment_id)

    return templates.TemplateResponse("otp-page.html", {
        "request": request,
        "payment_id": payment_id,
        "email": payment.otp_email
    })


@router.post("/otp/verify/{payment_id}")
async def verify_otp(
        request: Request,
        payment_id: str,
        background_tasks: BackgroundTasks,
        otp_code: str = Form(...),
        db: AsyncSession = Depends(get_db)
):
    from app.api.routes.payments import finalize_successful_payment

    logger.info(f"Verifying OTP for {payment_id}")
    payment = await get_payment(db, payment_id)

    if not payment:
        raise PaymentNotFoundError(payment_id)

    if not payment.otp_code or payment.otp_code != otp_code:
        logger.warning(f"Invalid OTP for {payment_id}")
        raise InvalidOTPError(payment_id)

    payment.otp_code = None
    await finalize_successful_payment(payment, db, background_tasks)

    response = RedirectResponse(url=f"/success/{payment_id}", status_code=303)
    response.set_cookie(
        key="user_email",
        value=payment.otp_email,
        max_age=2592000,
        httponly=True,
        secure=True,
        samesite="Strict"
    )
    return response


@router.get("/success/{payment_id}", response_class=HTMLResponse)
async def payment_success(payment_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    payment = await get_payment(db, payment_id)

    if not payment:
        raise PaymentNotFoundError(payment_id)

    return templates.TemplateResponse("success-page.html", {
        "request": request,
        "payment_id": payment.id,
        "amount": payment.amount,
        "reference": payment.reference,
        "card_mask": payment.card_mask,
        "redirect_url": payment.redirect_url,
        "currency_symbol": CURRENCY_SYMBOL
    })