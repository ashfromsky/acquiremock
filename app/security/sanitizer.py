import re
from html import escape
from urllib.parse import urlparse

from app.security.ssrf import validate_webhook_url

_EMAIL_RE = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")
_MAX_URL_LENGTH = 2048
_MAX_REFERENCE_LENGTH = 120
_MAX_EMAIL_LENGTH = 254


def _has_control_chars(value: str) -> bool:
    return any(ord(ch) < 32 or ord(ch) == 127 for ch in value)


def clean_input(text: str) -> str:
    if not text:
        return ""
    safe_text = escape(text)
    safe_text = re.sub(r"javascript:", "", safe_text, flags=re.IGNORECASE)
    return safe_text.strip()


def validate_reference(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("Invalid reference")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("Reference cannot be empty")
    if len(cleaned) > _MAX_REFERENCE_LENGTH:
        raise ValueError(f"Reference must be {_MAX_REFERENCE_LENGTH} characters or fewer")
    if _has_control_chars(cleaned):
        raise ValueError("Reference contains invalid control characters")
    return cleaned


def validate_email(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("Invalid email address")
    cleaned = value.strip().lower()
    if not cleaned or len(cleaned) > _MAX_EMAIL_LENGTH or _has_control_chars(cleaned):
        raise ValueError("Invalid email address")
    if not _EMAIL_RE.match(cleaned):
        raise ValueError("Invalid email address")
    return cleaned


def validate_redirect_url(url: str) -> str:
    if not isinstance(url, str):
        raise ValueError("Invalid redirect URL")
    cleaned = url.strip()
    if (
        not cleaned
        or len(cleaned) > _MAX_URL_LENGTH
        or any(ord(ch) < 32 or ord(ch) == 127 or ch.isspace() for ch in cleaned)
    ):
        raise ValueError("Invalid redirect URL: must use http or https")

    parsed = urlparse(cleaned)
    if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc or not parsed.hostname:
        raise ValueError("Invalid redirect URL: must use http or https")
    if parsed.username is not None or parsed.password is not None or "@" in parsed.netloc:
        raise ValueError("Invalid redirect URL: embedded credentials are not allowed")
    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Invalid redirect URL port") from exc
    if port is not None and not (1 <= port <= 65535):
        raise ValueError("Invalid redirect URL port")
    return cleaned


__all__ = [
    "clean_input",
    "validate_email",
    "validate_redirect_url",
    "validate_reference",
    "validate_webhook_url",
]
