import uuid
import httpx
import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict
import os
from dotenv import load_dotenv

from fastapi import FastAPI, HTTPException, Request, Form, BackgroundTasks, Depends, Query, Cookie, Body, Header
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel
import aiosmtplib
import asyncio

from models.invoice import CreateInvoiceResponse, CreateInvoiceRequest
from models.errors import (
    PaymentError, PaymentNotFoundError, PaymentAlreadyProcessedError,
    PaymentExpiredError, InsufficientFundsError, InvalidOTPError,
    CSRFTokenMismatchError, InvalidCardError, SavedCardNotFoundError
)
from other.miscFunctions import validate_otp
from security.crypto import generate_secure_otp, generate_csrf_token, hash_sensitive_data, verify_sensitive_data
from services.smtp_service import send_otp_email, send_receipt_email
from services.webhook_service import send_webhook_with_retry, verify_webhook_signature
from services.background_tasks import start_background_tasks
from database.chore.session import get_db, engine
from database.models.main_models import SuccessFulOperation, SavedCard, Payment
from database.functional.main_functions import (
    send_successful_operation, init_db, create_payment, get_payment,
    update_payment, get_payment_by_idempotency
)
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from security.middleware import SecurityHeadersMiddleware
from security.sanitizer import clean_input

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(title="AcquireMock", version="2.0.0")

login_store: Dict[str, str] = {}

load_dotenv()

BASE_URL = os.getenv('BASE_URL', 'http://localhost:8000')

class EmailRequest(BaseModel):
    email: str


class VerifyCodeRequest(BaseModel):
    email: str
    code: str


@app.on_event("startup")
async def on_startup():
    logger.info("Starting up application and initializing database...")
    await init_db(engine)
    logger.info("Database initialized successfully.")
    asyncio.create_task(start_background_tasks())
    logger.info("Background tasks started")


app.add_middleware(SecurityHeadersMiddleware)

templates = Jinja2Templates(directory="templates/pages")
app.mount("/static", StaticFiles(directory="static"), name="static")

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.exception_handler(PaymentError)
async def payment_error_handler(request: Request, exc: PaymentError):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.code,
            "message": exc.message,
            "payment_id": exc.payment_id
        }
    )


@app.get("/", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/test", response_class=HTMLResponse)
async def test_page(request: Request):
    return templates.TemplateResponse("test.html", {"request": request})


@app.get("/merchant/login", response_class=HTMLResponse)
async def merchant_login(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/merchant/dashboard", response_class=HTMLResponse)
async def merchant_dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})


@app.exception_handler(404)
async def custom_404_handler(request: Request, exc: HTTPException):
    return templates.TemplateResponse("404.html", {"request": request}, status_code=404)


async def get_user_data(email: str, db: AsyncSession):
    if not email: return [], []
    op_query = select(SuccessFulOperation).where(SuccessFulOperation.email == email).order_by(
        SuccessFulOperation.id.desc()).limit(5)
    op_result = await db.execute(op_query)

    card_query = select(SavedCard).where(SavedCard.email == email).order_by(SavedCard.id.desc())
    card_result = await db.execute(card_query)

    return op_result.scalars().all(), card_result.scalars().all()


async def finalize_successful_payment(
        payment: Payment,
        db: AsyncSession,
        background_tasks: BackgroundTasks
):
    logger.info(f"Finalizing payment {payment.id}")
    payment.status = "paid"
    payment.paid_at = datetime.utcnow()
    await update_payment(db, payment)

    try:
        new_op = SuccessFulOperation(
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
            "card_mask": payment.card_mask
        })
        logger.info(f"Receipt email task added for {payment.otp_email}")

    background_tasks.add_task(send_webhook_with_retry, payment, db)


@app.post("/api/auth/send-code")
async def auth_send_code(req: EmailRequest, background_tasks: BackgroundTasks):
    logger.info(f"Auth code requested for {req.email}")
    code = generate_secure_otp()
    login_store[req.email] = code
    background_tasks.add_task(send_otp_email, req.email, code)
    return {"status": "sent", "message": "Code sent"}


@app.post("/api/auth/verify-code")
async def auth_verify_code(req: VerifyCodeRequest):
    logger.info(f"Verifying code for {req.email}")
    stored_code = login_store.get(req.email)

    if not stored_code:
        logger.warning(f"Code expired or not found for {req.email}")
        raise HTTPException(400, "Code expired or not found")

    if stored_code != req.code:
        logger.warning(f"Invalid code attempt for {req.email}")
        raise HTTPException(400, "Invalid code")

    del login_store[req.email]
    logger.info(f"User {req.email} verified successfully")
    return {"status": "ok", "message": "Verified"}


@app.get("/api/user-info")
async def get_user_info_api(email: str, db: AsyncSession = Depends(get_db)):
    operations, cards = await get_user_data(email, db)
    return {
        "operations": [
            {"reference": op.reference, "amount": op.amount, "card_mask": op.card_mask,
             "date": op.created_at.strftime("%Y-%m-%d %H:%M")}
            for op in operations
        ],
        "cards": [
            {"id": c.id, "mask": c.card_mask, "expiry": c.expiry}
            for c in cards
        ]
    }


@app.post("/api/create-invoice", response_model=CreateInvoiceResponse)
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


@app.get("/checkout/{payment_id}")
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

    response = templates.TemplateResponse("checkout.html", {
        "request": request,
        "payment_id": payment_id,
        "amount": payment.amount,
        "reference": payment.reference,
        "recent_operations": recent_operations,
        "saved_cards": saved_cards,
        "prefill_email": user_email,
        "csrf_token": csrf_token
    })

    response.set_cookie(
        key="csrf_token",
        value=csrf_token,
        httponly=True,
        secure=True,
        samesite="Strict"
    )
    return response


@app.post("/pay/{payment_id}")
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


@app.get("/otp/{payment_id}")
async def otp_page(payment_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    payment = await get_payment(db, payment_id)

    if not payment or payment.status != "waiting_for_otp":
        raise HTTPException(400, "Invalid state")

    return templates.TemplateResponse("otp-page.html",
                                      {"request": request, "payment_id": payment_id, "email": payment.otp_email})


@app.post("/otp/verify/{payment_id}")
async def verify_otp(
        request: Request,
        payment_id: str,
        background_tasks: BackgroundTasks,
        otp_code: str = Form(...),
        db: AsyncSession = Depends(get_db)
):
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


@app.get("/success/{payment_id}")
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
        "redirect_url": payment.redirect_url
    })


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0.0"
    }


@app.post("/webhooks/verify")
async def verify_webhook(request: Request):
    data = await request.json()
    signature = request.headers.get("X-Signature")

    if not signature:
        raise HTTPException(400, "Missing signature")

    is_valid = verify_webhook_signature(data, signature)

    return {"valid": is_valid}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)