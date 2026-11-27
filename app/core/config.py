import hmac
import os
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

_WEAK_SECRET_VALUES = {
    "change_this_secret_key_min_32_characters",
    "your_super_secret_string_min_32_chars_change_this_in_production",
    "your_webhook_secret_here",
    "your_session_secret_here",
    "changeme",
    "secret",
    "password",
    "test-secret",
    "default-secret",
}


def validate_secret(name: str, value: Optional[str]) -> str:
    if not value or not value.strip():
        raise EnvironmentError(f"CRITICAL: {name} must be set as an environment variable.")
    if len(value) < 32:
        raise EnvironmentError(f"CRITICAL: {name} must be at least 32 characters long.")
    if value.strip().lower() in _WEAK_SECRET_VALUES:
        raise EnvironmentError(f"CRITICAL: {name} uses a forbidden default or placeholder value.")
    if len(set(value)) < 4:
        raise EnvironmentError(f"CRITICAL: {name} has insufficient entropy.")
    return value


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        parsed = int(raw.strip())
    except ValueError as exc:
        raise EnvironmentError(f"CRITICAL: {name} must be an integer.") from exc
    if parsed < minimum:
        raise EnvironmentError(f"CRITICAL: {name} must be >= {minimum}.")
    return parsed


BASE_URL = os.getenv("BASE_URL", "http://localhost:8000").rstrip("/")
CURRENCY_CODE = os.getenv("CURRENCY_CODE", "USD").strip().upper()
CURRENCY_SYMBOL = os.getenv("CURRENCY_SYMBOL", "$")

WEBHOOK_SECRET = validate_secret("WEBHOOK_SECRET", os.getenv("WEBHOOK_SECRET"))
SESSION_SECRET = validate_secret("SESSION_SECRET", os.getenv("SESSION_SECRET"))
if hmac.compare_digest(WEBHOOK_SECRET, SESSION_SECRET):
    raise EnvironmentError("CRITICAL: SESSION_SECRET must be distinct from WEBHOOK_SECRET.")

ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "").strip()
ADMIN_PASSWORD_HASH = os.getenv("ADMIN_PASSWORD_HASH", "").strip()


def is_admin_configured() -> bool:
    return (
        bool(ADMIN_USERNAME)
        and ADMIN_PASSWORD_HASH.startswith(("$2a$", "$2b$", "$2y$"))
        and len(ADMIN_PASSWORD_HASH) >= 59
    )


ADMIN_SESSION_TTL_SECONDS = _env_int("ADMIN_SESSION_TTL_SECONDS", 28800, minimum=60)
CUSTOMER_SESSION_TTL_SECONDS = _env_int("CUSTOMER_SESSION_TTL_SECONDS", 2592000, minimum=60)
PAYMENT_TTL_MINUTES = _env_int("PAYMENT_TTL_MINUTES", 15, minimum=1)
WEBHOOK_MAX_ATTEMPTS = _env_int("WEBHOOK_MAX_ATTEMPTS", 5, minimum=1)
WEBHOOK_TIMEOUT_SECONDS = _env_int("WEBHOOK_TIMEOUT_SECONDS", 10, minimum=1)

COOKIE_SECURE = BASE_URL.startswith("https://")
ALLOW_LOCAL_WEBHOOKS = os.getenv("ALLOW_LOCAL_WEBHOOKS", "false").lower() == "true"
ENABLE_EMBEDDED_WORKER = os.getenv("ENABLE_EMBEDDED_WORKER", "false").lower() == "true"
