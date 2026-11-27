from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import COOKIE_SECURE, CURRENCY_CODE, CURRENCY_SYMBOL
from app.core.currency import format_minor_amount
from app.database.core.session import get_db
from app.functional.main_functions import get_payment, get_user_data
from app.models.errors import PaymentAlreadyProcessedError, PaymentExpiredError, PaymentNotFoundError
from app.security.crypto import generate_csrf_token, verify_signed_email_token
from app.services.payments.lifecycle import expire_payment_if_needed

import logging

logger = logging.getLogger(__name__)
templates = Jinja2Templates(directory="templates/pages")

router = APIRouter(
    tags=["checkout"],
)


@router.get("/checkout/{payment_id}", response_class=HTMLResponse)
async def checkout(payment_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    payment = await get_payment(db, payment_id)

    if not payment:
        raise PaymentNotFoundError(payment_id)

    if payment.status in ["paid", "expired", "failed"]:
        raise PaymentAlreadyProcessedError(payment_id)

    if await expire_payment_if_needed(db, payment):
        raise PaymentExpiredError(payment_id)

    user_email = verify_signed_email_token(request.cookies.get("user_session"))
    recent_operations, saved_cards = [], []
    csrf_token = generate_csrf_token()

    if user_email:
        recent_operations, saved_cards = await get_user_data(user_email, db)

    response = templates.TemplateResponse(request, "checkout.html", {
        "request": request,
        "payment_id": payment_id,
        "amount": payment.amount,
        "formatted_amount": format_minor_amount(payment.amount, CURRENCY_CODE, CURRENCY_SYMBOL),
        "reference": payment.reference,
        "recent_operations": recent_operations,
        "saved_cards": saved_cards,
        "prefill_email": user_email,
        "csrf_token": csrf_token,
        "currency_symbol": CURRENCY_SYMBOL
    })

    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="Strict"
    )
    return response