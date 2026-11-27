import logging
import time
import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

import app.core.config as config
from app.core.limiter import limiter
from app.core.time import utcnow
from app.database.core.session import get_db
from app.models.main_models import AdminSession
from app.security.admin_auth import (
    get_active_admin_session,
    require_admin_csrf,
    verify_admin_credentials,
)
from app.security.crypto import create_admin_session_token, generate_csrf_token

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
)


class AdminLoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=120)
    password: str = Field(..., min_length=1, max_length=256)


@router.post("/login")
@limiter.limit("5/minute")
async def admin_login(
    request: Request,
    response: Response,
    payload: AdminLoginRequest,
    db: AsyncSession = Depends(get_db),
):
    if not config.is_admin_configured():
        raise HTTPException(
            status_code=503,
            detail="Administrator authentication is not configured",
        )

    if not verify_admin_credentials(payload.username, payload.password):
        logger.warning("Failed administrator login attempt")
        raise HTTPException(status_code=401, detail="Invalid administrator credentials")

    now = utcnow()
    expires_at = now + timedelta(seconds=config.ADMIN_SESSION_TTL_SECONDS)
    exp_ts = int(time.time()) + config.ADMIN_SESSION_TTL_SECONDS
    session_id = str(uuid.uuid4())
    csrf_token = generate_csrf_token()

    admin_session = AdminSession(
        session_id=session_id,
        username=config.ADMIN_USERNAME,
        csrf_token=csrf_token,
        expires_at=expires_at,
        created_at=now,
    )
    db.add(admin_session)
    await db.commit()

    signed_token = create_admin_session_token(
        username=config.ADMIN_USERNAME,
        session_id=session_id,
        csrf_token=csrf_token,
        expires_at=exp_ts,
    )

    response.set_cookie(
        key="admin_session",
        value=signed_token,
        max_age=config.ADMIN_SESSION_TTL_SECONDS,
        httponly=True,
        secure=config.COOKIE_SECURE,
        samesite="lax",
        path="/",
    )
    response.set_cookie(
        key="admin_csrf",
        value=csrf_token,
        max_age=config.ADMIN_SESSION_TTL_SECONDS,
        httponly=False,
        secure=config.COOKIE_SECURE,
        samesite="lax",
        path="/",
    )
    logger.info("Administrator session created for %s", config.ADMIN_USERNAME)
    return {
        "authenticated": True,
        "username": config.ADMIN_USERNAME,
        "csrf_token": csrf_token,
        "expires_at": expires_at.isoformat(),
        "configured": True,
    }


@router.post("/logout")
async def admin_logout(
    response: Response,
    admin_session: AdminSession = Depends(require_admin_csrf),
    db: AsyncSession = Depends(get_db),
):
    admin_session.revoked_at = utcnow()
    db.add(admin_session)
    await db.commit()

    response.delete_cookie("admin_session", path="/")
    response.delete_cookie("admin_csrf", path="/")
    return {"status": "ok"}


@router.get("/session")
async def admin_session_status(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    configured = config.is_admin_configured()
    if not configured:
        return {
            "authenticated": False,
            "username": None,
            "csrf_token": None,
            "expires_at": None,
            "configured": False,
        }

    session = await get_active_admin_session(request, db)
    if not session:
        return {
            "authenticated": False,
            "username": None,
            "csrf_token": None,
            "expires_at": None,
            "configured": True,
        }

    return {
        "authenticated": True,
        "username": session.username,
        "csrf_token": session.csrf_token,
        "expires_at": session.expires_at.isoformat(),
        "configured": True,
    }
