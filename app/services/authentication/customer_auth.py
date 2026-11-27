import hashlib
import hmac
from datetime import timedelta

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import delete, select

import app.core.config as config
from app.core.time import utcnow
from app.models.main_models import AuthChallenge
from app.security.crypto import generate_secure_otp
from app.security.sanitizer import validate_email

MAX_AUTH_OTP_ATTEMPTS = 5
AUTH_OTP_TTL_MINUTES = 10


def _hash_auth_code(email: str, code: str) -> str:
    message = f"auth-otp|{email}|{code}".encode("utf-8")
    return hmac.new(
        config.SESSION_SECRET.encode("utf-8"),
        message,
        hashlib.sha256,
    ).hexdigest()


async def cleanup_expired_auth_challenges(db: AsyncSession) -> int:
    result = await db.execute(
        delete(AuthChallenge).where(AuthChallenge.expires_at <= utcnow())
    )
    await db.commit()
    return int(result.rowcount or 0)


async def issue_auth_challenge(db: AsyncSession, raw_email: str) -> tuple[str, str]:
    email = validate_email(raw_email)
    now = utcnow()
    code = generate_secure_otp()
    code_hash = _hash_auth_code(email, code)
    expires_at = now + timedelta(minutes=AUTH_OTP_TTL_MINUTES)

    await db.execute(delete(AuthChallenge).where(AuthChallenge.expires_at <= now))

    existing = (
        await db.execute(select(AuthChallenge).where(AuthChallenge.email == email))
    ).scalars().first()
    if existing:
        existing.code_hash = code_hash
        existing.attempts = 0
        existing.expires_at = expires_at
        existing.updated_at = now
        db.add(existing)
    else:
        db.add(
            AuthChallenge(
                email=email,
                code_hash=code_hash,
                attempts=0,
                expires_at=expires_at,
                created_at=now,
                updated_at=now,
            )
        )

    await db.commit()
    return email, code


async def verify_auth_challenge(db: AsyncSession, raw_email: str, raw_code: str) -> str:
    email = validate_email(raw_email)
    code = raw_code.strip()
    now = utcnow()

    entry = (
        await db.execute(select(AuthChallenge).where(AuthChallenge.email == email))
    ).scalars().first()

    if not entry:
        raise HTTPException(400, "Code expired or not found")

    if entry.expires_at <= now:
        await db.delete(entry)
        await db.commit()
        raise HTTPException(400, "Code expired or not found")

    expected_hash = _hash_auth_code(email, code)
    if not hmac.compare_digest(entry.code_hash, expected_hash):
        entry.attempts += 1
        entry.updated_at = now
        if entry.attempts >= MAX_AUTH_OTP_ATTEMPTS:
            await db.delete(entry)
            await db.commit()
            raise HTTPException(429, "Too many invalid attempts")
        db.add(entry)
        await db.commit()
        raise HTTPException(400, "Invalid code")

    await db.delete(entry)
    await db.commit()
    return email
