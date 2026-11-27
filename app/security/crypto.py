import base64
import hashlib
import hmac
import secrets
import string
import time
from typing import Optional

from passlib.context import CryptContext

from app.core.config import WEBHOOK_SECRET

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _session_signing_key() -> bytes:
    return hmac.new(WEBHOOK_SECRET.encode(), b"acquiremock-session", hashlib.sha256).digest()


def generate_secure_otp(length: int = 4) -> str:
    return ''.join(secrets.choice(string.digits) for _ in range(length))


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def hash_sensitive_data(data: str) -> str:
    return pwd_context.hash(data)


def verify_sensitive_data(plain_data: str, hashed_data: str) -> bool:
    return pwd_context.verify(plain_data, hashed_data)


def create_signed_email_token(email: str, max_age_seconds: int = 2592000) -> str:
    expires_at = int(time.time()) + max_age_seconds
    payload_bytes = f"{email}|{expires_at}".encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_bytes).decode("ascii")
    signature = hmac.new(_session_signing_key(), payload_b64.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{signature}"


def verify_signed_email_token(token: Optional[str]) -> Optional[str]:
    if not token or "." not in token:
        return None

    try:
        payload_b64, signature = token.rsplit(".", 1)
        expected = hmac.new(_session_signing_key(), payload_b64.encode("ascii"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            return None

        decoded = base64.urlsafe_b64decode(payload_b64.encode("ascii")).decode("utf-8")
        email, exp_str = decoded.rsplit("|", 1)
        if int(exp_str) <= int(time.time()) or not email:
            return None
        return email
    except Exception:
        return None
