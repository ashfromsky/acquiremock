import hmac
import logging
from datetime import datetime, timedelta
from typing import Any, Dict

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response
from pydantic import BaseModel

from app.core.config import COOKIE_SECURE
from app.core.limiter import limiter
from app.security.crypto import create_signed_email_token, generate_secure_otp, verify_signed_email_token
from app.services.smtp_service import send_otp_email

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/auth",
    tags=["authentication"],
)

MAX_OTP_ATTEMPTS = 5
OTP_TTL_MINUTES = 10
login_store: Dict[str, Dict[str, Any]] = {}


class EmailRequest(BaseModel):
    email: str


class VerifyCodeRequest(BaseModel):
    email: str
    code: str


@router.post("/send-code")
@limiter.limit("5/minute")
async def auth_send_code(request: Request, req: EmailRequest, background_tasks: BackgroundTasks):
    logger.info(f"Auth code requested for {req.email}")
    code = generate_secure_otp()
    login_store[req.email] = {
        "code": code,
        "expires_at": datetime.utcnow() + timedelta(minutes=OTP_TTL_MINUTES),
        "attempts": 0,
    }
    background_tasks.add_task(send_otp_email, req.email, code)
    return {"status": "sent", "message": "Code sent"}


@router.post("/verify-code")
@limiter.limit("10/minute")
async def auth_verify_code(request: Request, response: Response, req: VerifyCodeRequest):
    logger.info(f"Verifying code for {req.email}")
    entry = login_store.get(req.email)

    if not entry:
        logger.warning(f"Code expired or not found for {req.email}")
        raise HTTPException(400, "Code expired or not found")

    if entry["expires_at"] < datetime.utcnow():
        del login_store[req.email]
        logger.warning(f"Code expired for {req.email}")
        raise HTTPException(400, "Code expired or not found")

    if not hmac.compare_digest(entry["code"], req.code):
        entry["attempts"] += 1
        logger.warning(f"Invalid code attempt for {req.email}")
        if entry["attempts"] >= MAX_OTP_ATTEMPTS:
            del login_store[req.email]
            raise HTTPException(429, "Too many invalid attempts")
        raise HTTPException(400, "Invalid code")

    del login_store[req.email]
    response.set_cookie(
        key="user_session",
        value=create_signed_email_token(req.email),
        max_age=2592000,
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="lax",
    )
    logger.info(f"User {req.email} verified successfully")
    return {"status": "ok", "message": "Verified"}


@router.get("/session")
async def auth_session(request: Request):
    email = verify_signed_email_token(request.cookies.get("user_session"))
    return {"authenticated": bool(email), "email": email}


@router.post("/logout")
async def auth_logout(response: Response):
    response.delete_cookie("user_session", path="/")
    return {"status": "ok"}
