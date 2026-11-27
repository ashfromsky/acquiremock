import hmac
from typing import Optional

from fastapi import Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

import app.core.config as config
from app.core.time import utcnow
from app.database.core.session import get_db
from app.models.errors import CSRFTokenMismatchError
from app.models.main_models import AdminSession
from app.security.crypto import verify_admin_session_token, verify_sensitive_data

_DUMMY_BCRYPT_HASH = "$2b$12$C6UzMDM.H6dfI/f/IKcEeO6Q9e2oY2y9lP5dQ0zP0nQ4V9sQ6e0eK"


def verify_admin_credentials(username: str, password: str) -> bool:
    if not config.is_admin_configured():
        return False

    username_ok = hmac.compare_digest(username.strip(), config.ADMIN_USERNAME)
    password_ok = verify_sensitive_data(password, config.ADMIN_PASSWORD_HASH or _DUMMY_BCRYPT_HASH)
    return username_ok and password_ok


async def get_active_admin_session(
    request: Request,
    db: AsyncSession,
) -> Optional[AdminSession]:
    if not config.is_admin_configured():
        return None

    token = request.cookies.get("admin_session")
    payload = verify_admin_session_token(token)
    if not payload:
        return None

    session_id = payload["jti"]
    token_username = payload["sub"]
    token_csrf = payload["csrf"]

    if not hmac.compare_digest(token_username, config.ADMIN_USERNAME):
        return None

    result = await db.execute(
        select(AdminSession).where(AdminSession.session_id == session_id)
    )
    record = result.scalars().first()
    if not record:
        return None
    if record.revoked_at is not None or record.expires_at <= utcnow():
        return None
    if not hmac.compare_digest(record.username, config.ADMIN_USERNAME):
        return None
    if not hmac.compare_digest(record.csrf_token, token_csrf):
        return None

    return record


async def require_admin(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AdminSession:
    if not config.is_admin_configured():
        raise HTTPException(
            status_code=503,
            detail="Administrator authentication is not configured",
        )

    session = await get_active_admin_session(request, db)
    if not session:
        raise HTTPException(
            status_code=401,
            detail="Administrator authentication required",
        )
    return session


async def require_admin_csrf(
    request: Request,
    admin_session: AdminSession = Depends(require_admin),
) -> AdminSession:
    header_token = request.headers.get("X-CSRF-Token")
    if not header_token or not hmac.compare_digest(header_token, admin_session.csrf_token):
        raise CSRFTokenMismatchError()

    cookie_token = request.cookies.get("admin_csrf")
    if cookie_token is not None and not hmac.compare_digest(cookie_token, admin_session.csrf_token):
        raise CSRFTokenMismatchError()

    return admin_session
