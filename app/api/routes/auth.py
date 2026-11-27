import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response
from pydantic import BaseModel, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

import app.core.config as config
from app.core.limiter import get_auth_email_key, limiter
from app.database.core.session import get_db
from app.security.crypto import create_signed_email_token, verify_signed_email_token
from app.security.sanitizer import validate_email
from app.services.authentication.customer_auth import (
    issue_auth_challenge,
    verify_auth_challenge,
)
from app.services.smtp_service import send_otp_email

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/auth",
    tags=["authentication"],
)


class EmailRequest(BaseModel):
    email: str

    @field_validator("email")
    @classmethod
    def check_email(cls, value: str) -> str:
        return validate_email(value)


class VerifyCodeRequest(BaseModel):
    email: str
    code: str

    @field_validator("email")
    @classmethod
    def check_email(cls, value: str) -> str:
        return validate_email(value)


@router.post("/send-code")
@limiter.limit("5/minute", key_func=get_auth_email_key)
async def auth_send_code(
    request: Request,
    req: EmailRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    logger.info("Auth code requested for %s", req.email)
    email, code = await issue_auth_challenge(db, req.email)
    background_tasks.add_task(send_otp_email, email, code)
    return {"status": "sent", "message": "Code sent"}


@router.post("/verify-code")
@limiter.limit("10/minute", key_func=get_auth_email_key)
async def auth_verify_code(
    request: Request,
    response: Response,
    req: VerifyCodeRequest,
    db: AsyncSession = Depends(get_db),
):
    logger.info("Verifying auth code for %s", req.email)
    verified_email = await verify_auth_challenge(db, req.email, req.code)
    response.set_cookie(
        key="user_session",
        value=create_signed_email_token(verified_email),
        max_age=config.CUSTOMER_SESSION_TTL_SECONDS,
        httponly=True,
        secure=config.COOKIE_SECURE,
        samesite="lax",
        path="/",
    )
    logger.info("User %s verified successfully", verified_email)
    return {"status": "ok", "message": "Verified"}


@router.get("/session")
async def auth_session(request: Request):
    email = verify_signed_email_token(request.cookies.get("user_session"))
    return {"authenticated": bool(email), "email": email}


@router.post("/logout")
async def auth_logout(response: Response):
    response.delete_cookie("user_session", path="/")
    return {"status": "ok"}
