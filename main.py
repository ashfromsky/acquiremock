import uuid
import httpx
import logging
from datetime import datetime
from typing import List, Optional, Dict

from fastapi import FastAPI, HTTPException, Request, Form, BackgroundTasks, Depends, Query, Cookie, Body
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel
import aiosmtplib

from models.invoice import CreateInvoiceResponse, CreateInvoiceRequest
from other.data import db_payments
from other.miscFunctions import payment_check, validate_otp
from security.crypto import generate_secure_otp, generate_csrf_token
from services.smtp_service import send_otp_email, send_receipt_email
from database.chore.session import get_db, engine
from database.models.main_models import SuccessFulOperation, SavedCard
from database.functional.main_functions import send_successful_operation, init_db
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from security.middleware import SecurityHeadersMiddleware
from security.sanitizer import clean_input
from security.crypto import generate_secure_otp

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(title="AcquireMock", version="1.0.0")

login_store: Dict[str, str] = {}


class EmailRequest(BaseModel):
    email: str


class VerifyCodeRequest(BaseModel):
    email: str
    code: str


@app.on_event("startup")
async def on_startup():
    logger.info("Starting up application (v 1.0.1) and initializing database...")
    await init_db(engine)
    logger.info("Database initialized successfully.")


app.add_middleware(SecurityHeadersMiddleware)

templates = Jinja2Templates(directory="templates/pages")
app.mount("/static", StaticFiles(directory="static"), name="static")

limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

@app.get("/", response_class=HTMLResponse)
@limiter.limit("10/minute")
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/test", response_class=HTMLResponse)
async def test_page(request: Request):
    return templates.TemplateResponse("test.html", {"request": request})

@app.exception_handler(404)
async def custom_404_handler(request: Request, exc: HTTPException):
    return templates.TemplateResponse("404.html", {"request": request}, status_code=404)



async def send_webhook(payment_id: str, payment: dict):
    webhook_url = payment.get("webhook_url")
    if not webhook_url:
        logger.warning(f"No webhook URL for payment {payment_id}")
        return

    webhook_data = {
        "payment_id": payment_id,
        "reference": payment["reference"],
        "amount": payment["amount"],
        "status": "success"
    }

    logger.info(f"Sending webhook to {webhook_url} for payment {payment_id}")
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(webhook_url, json=webhook_data)
            logger.info(f"Webhook sent. Status: {resp.status_code}")
    except Exception as e:
        logger.error(f"Failed to send webhook for {payment_id}: {e}")


async def get_user_data(email: str, db: AsyncSession):
    if not email: return [], []
    op_query = select(SuccessFulOperation).where(SuccessFulOperation.email == email).order_by(
        SuccessFulOperation.id.desc()).limit(5)
    op_result = await db.execute(op_query)

    card_query = select(SavedCard).where(SavedCard.email == email).order_by(SavedCard.id.desc())
    card_result = await db.execute(card_query)

    return op_result.scalars().all(), card_result.scalars().all()


async def finalize_successful_payment(payment_id: str, payment: dict, db: AsyncSession,
                                      background_tasks: BackgroundTasks):
    logger.info(f"Finalizing payment {payment_id}")
    payment["status"] = "paid"
    payment["paid_at"] = datetime.now().isoformat()
    payment["payment_id"] = payment_id

    try:
        new_op = SuccessFulOperation(
            payment_id=payment_id,
            email=payment.get("otp_email"),
            amount=payment["amount"],
            reference=payment["reference"],
            card_mask=payment.get("card_mask"),
            redirect_url=payment.get("redirect_url", "")
        )
        await send_successful_operation(db, new_op)
        logger.info(f"Operation {payment_id} saved to DB")

        temp_data = payment.get("temp_card_data", {})
        if temp_data.get("save"):
            existing = await db.execute(select(SavedCard).where(
                SavedCard.email == payment.get("otp_email"),
                SavedCard.card_mask == payment.get("card_mask")
            ))
            if not existing.scalars().first():
                saved_card = SavedCard(
                    email=payment.get("otp_email"),
                    card_number=temp_data["number"],
                    expiry=temp_data["expiry"],
                    cvv=temp_data["cvv"],
                    card_mask=payment.get("card_mask")
                )
                db.add(saved_card)
                await db.commit()
                logger.info(f"Card saved for user {payment.get('otp_email')}")
    except Exception as e:
        logger.error(f"DB Error during finalization: {e}")

    if payment.get("otp_email"):
        background_tasks.add_task(send_receipt_email, payment.get("otp_email"), payment)
        logger.info(f"Receipt email task added for {payment.get('otp_email')}")

    background_tasks.add_task(send_webhook, payment_id, payment)


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
            {"id": c.id, "mask": c.card_mask, "number": c.card_number, "expiry": c.expiry, "cvv": c.cvv}
            for c in cards
        ]
    }


@app.post("/api/create-invoice", response_model=CreateInvoiceResponse)
async def create_invoice(invoice: CreateInvoiceRequest):
    clean_reference = clean_input(invoice.reference)

    logger.info(f"Creating invoice for amount {invoice.amount}, ref {clean_reference}")
    payment_id = str(uuid.uuid4())

    db_payments[payment_id] = {
        "amount": invoice.amount,
        "reference": clean_reference,
        "webhook_url": invoice.webhook_url,
        "redirect_url": invoice.redirect_url,
        "status": "pending",
        "created_at": datetime.now().isoformat()
    }
    page_url = f"http://localhost:8002/checkout/{payment_id}"
    logger.info(f"Invoice created: {payment_id}")
    return CreateInvoiceResponse(pageUrl=page_url)


@app.get("/checkout/{payment_id}")
async def checkout(payment_id: str, request: Request, db: AsyncSession = Depends(get_db)):
    payment = payment_check(payment_id, db_payments)
    if not isinstance(payment, dict):
        logger.warning(f"Checkout failed: Payment {payment_id} not found")
        raise HTTPException(404, "Payment not found")

    user_email = request.cookies.get("user_email")
    recent_operations, saved_cards = [], []

    csrf_token = generate_csrf_token()

    if user_email:
        recent_operations, saved_cards = await get_user_data(user_email, db)

    response = templates.TemplateResponse("checkout.html", {
        "request": request,
        "payment_id": payment_id,
        "amount": payment["amount"],
        "reference": payment["reference"],
        "recent_operations": recent_operations,
        "saved_cards": saved_cards,
        "prefill_email": user_email,
        "csrf_token": csrf_token
    })

    response.set_cookie(key="csrf_token", value=csrf_token, httponly=True)
    return response


@app.post("/pay/{payment_id}")
async def process_payment(
        request: Request,
        payment_id: str,
        background_tasks: BackgroundTasks,
        card_number: str = Form(...),
        expiry: str = Form(...),
        cvv: str = Form(...),
        email: str = Form(...),
        save_card: bool = Form(False),
        csrf_token: str = Form(...),
        db: AsyncSession = Depends(get_db)
):
    cookie_token = request.cookies.get("csrf_token")
    if not cookie_token or cookie_token != csrf_token:
        logger.warning(f"CSRF Attack attempt on payment {payment_id}")
        raise HTTPException(status_code=403, detail="CSRF Token Mismatch")

    logger.info(f"Processing payment {payment_id} for email {email}")
    payment = payment_check(payment_id, db_payments)
    if not isinstance(payment, dict):
        raise HTTPException(404, "Payment error")

    card_number_clean = card_number.replace(" ", "")

    if card_number_clean == "4444444444444444":
        payment.update({
            "otp_email": email,
            "card_mask": f"**** {card_number_clean[-4:]}",
            "temp_card_data": {
                "number": card_number,
                "expiry": expiry,
                "cvv": cvv,
                "save": save_card
            }
        })

        cookie_email = request.cookies.get("user_email")
        if cookie_email and cookie_email == email:
            logger.info(f"Cookie matched for {email}, skipping OTP")
            await finalize_successful_payment(payment_id, payment, db, background_tasks)
            return RedirectResponse(url=f"/success/{payment_id}", status_code=303)

        otp_code = generate_secure_otp()
        payment["otp_code"] = otp_code
        payment["status"] = "waiting_for_otp"

        background_tasks.add_task(send_otp_email, email, otp_code)
        logger.info(f"OTP sent to {email}")
        return RedirectResponse(url=f"/otp/{payment_id}", status_code=303)
    else:
        logger.warning(f"Insufficient funds for payment {payment_id}")
        raise HTTPException(400, "Insufficient funds")


@app.get("/otp/{payment_id}")
async def otp_page(payment_id: str, request: Request):
    payment = payment_check(payment_id, db_payments)
    if not isinstance(payment, dict) or payment.get("status") != "waiting_for_otp":
        raise HTTPException(400, "Invalid state")
    return templates.TemplateResponse("otp-page.html",
                                      {"request": request, "payment_id": payment_id, "email": payment.get("otp_email")})


@app.post("/otp/verify/{payment_id}")
async def verify_otp(
        request: Request,
        payment_id: str,
        background_tasks: BackgroundTasks,
        otp_code: str = Form(...),
        db: AsyncSession = Depends(get_db)
):
    logger.info(f"Verifying OTP for {payment_id}")
    payment = payment_check(payment_id, db_payments)
    if not isinstance(payment, dict) or not validate_otp(payment, otp_code):
        logger.warning(f"Invalid OTP for {payment_id}")
        raise HTTPException(400, "Invalid OTP")

    payment["otp_code"] = None
    await finalize_successful_payment(payment_id, payment, db, background_tasks)

    return RedirectResponse(url=f"/success/{payment_id}", status_code=303)


@app.get("/success/{payment_id}")
async def payment_success(payment_id: str, request: Request):
    if payment_id not in db_payments: raise HTTPException(404)
    return templates.TemplateResponse("success-page.html", {"request": request, **db_payments[payment_id]})


@app.get("/health")
async def health():
    return {"status": "ok"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8002, reload=True)