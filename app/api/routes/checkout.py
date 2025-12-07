import logging
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from app.functional.main_functions import get_user_data

from app.database.core.session import get_db
from app.functional.main_functions import get_payment, update_payment
from app.models.errors import PaymentNotFoundError, PaymentAlreadyProcessedError, PaymentExpiredError
from app.security.crypto import generate_csrf_token
from app.core.config import CURRENCY_SYMBOL

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

    if payment.expires_at < datetime.utcnow():
        payment.status = "expired"
        await update_payment(db, payment)
        raise PaymentExpiredError(payment_id)

    user_email = request.cookies.get("user_email")
    recent_operations, saved_cards = [], []
    csrf_token = generate_csrf_token()

    if user_email:
        recent_operations, saved_cards = await get_user_data(user_email, db)

    response = templates.TemplateResponse(request, "checkout.html", {
        "request": request,
        "payment_id": payment_id,
        "amount": payment.amount,
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
        secure=True,
        samesite="Strict"
    )
    return response