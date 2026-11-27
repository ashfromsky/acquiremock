import base64
import hashlib
import hmac
import json
import secrets
import string
import time
from typing import Any, Optional

import bcrypt

import app.core.config as config


def _customer_session_signing_key() -> bytes:
    return hmac.new(
        config.SESSION_SECRET.encode("utf-8"),
        b"acquiremock-customer-session-v2",
        hashlib.sha256,
    ).digest()


def _admin_session_signing_key() -> bytes:
    return hmac.new(
        config.SESSION_SECRET.encode("utf-8"),
        b"acquiremock-admin-session-v2",
        hashlib.sha256,
    ).digest()


def generate_secure_otp(length: int = 4) -> str:
    return "".join(secrets.choice(string.digits) for _ in range(length))


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def hash_sensitive_data(data: str) -> str:
    hashed = bcrypt.hashpw(data.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_sensitive_data(plain_data: str, hashed_data: str) -> bool:
    if not plain_data or not hashed_data:
        return False
    try:
        return bcrypt.checkpw(plain_data.encode("utf-8"), hashed_data.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def create_signed_email_token(
    email: str,
    max_age_seconds: int = config.CUSTOMER_SESSION_TTL_SECONDS,
) -> str:
    expires_at = int(time.time()) + max_age_seconds
    payload_bytes = f"{email}|{expires_at}".encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode("ascii")
    signature = hmac.new(
        _customer_session_signing_key(),
        payload_b64.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload_b64}.{signature}"


def verify_signed_email_token(token: Optional[str]) -> Optional[str]:
    if not token or "." not in token:
        return None

    try:
        payload_b64, signature = token.rsplit(".", 1)
        expected = hmac.new(
            _customer_session_signing_key(),
            payload_b64.encode("ascii"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, signature):
            return None

        decoded = base64.urlsafe_b64decode(payload_b64.encode("ascii")).decode("utf-8")
        email, exp_str = decoded.rsplit("|", 1)
        if int(exp_str) <= int(time.time()) or not email:
            return None
        return email
    except Exception:
        return None


def create_admin_session_token(
    username: str,
    session_id: str,
    csrf_token: str,
    expires_at: int,
) -> str:
    payload_obj = {
        "sub": username,
        "jti": session_id,
        "csrf": csrf_token,
        "exp": expires_at,
        "scope": "admin",
    }
    payload_bytes = json.dumps(payload_obj, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode("ascii")
    signature = hmac.new(
        _admin_session_signing_key(),
        payload_b64.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload_b64}.{signature}"


def verify_admin_session_token(token: Optional[str]) -> Optional[dict[str, Any]]:
    if not token or "." not in token:
        return None

    try:
        payload_b64, signature = token.rsplit(".", 1)
        expected = hmac.new(
            _admin_session_signing_key(),
            payload_b64.encode("ascii"),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, signature):
            return None

        decoded = base64.urlsafe_b64decode(payload_b64.encode("ascii")).decode("utf-8")
        payload = json.loads(decoded)
        if not isinstance(payload, dict):
            return None
        if payload.get("scope") != "admin":
            return None
        exp = payload.get("exp")
        if not isinstance(exp, int) or exp <= int(time.time()):
            return None
        for field in ("sub", "jti", "csrf"):
            val = payload.get(field)
            if not isinstance(val, str) or not val:
                return None
        return payload
    except Exception:
        return None
