import pytest

from app.core.config import is_admin_configured, validate_secret
from app.security.crypto import (
    create_admin_session_token,
    create_signed_email_token,
    hash_sensitive_data,
    verify_admin_session_token,
    verify_sensitive_data,
    verify_signed_email_token,
)


@pytest.mark.parametrize(
    "bad_secret",
    [
        None,
        "",
        "   ",
        "too-short",
        "change_this_secret_key_min_32_characters",
        "your_super_secret_string_min_32_chars_change_this_in_production",
        "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    ],
)
def test_validate_secret_rejects_weak_or_missing(bad_secret):
    with pytest.raises(EnvironmentError):
        validate_secret("SESSION_SECRET", bad_secret)


def test_validate_secret_accepts_strong_value():
    val = "unique-strong-secret-value-with-enough-entropy-9482"
    assert validate_secret("SESSION_SECRET", val) == val


def test_session_signing_uses_session_secret_not_webhook_secret(monkeypatch):
    import app.core.config as config

    token = create_signed_email_token("user@example.com")
    assert verify_signed_email_token(token) == "user@example.com"

    monkeypatch.setattr(config, "WEBHOOK_SECRET", "another-completely-different-webhook-secret-9999")
    assert verify_signed_email_token(token) == "user@example.com"

    monkeypatch.setattr(config, "SESSION_SECRET", "rotated-session-secret-that-breaks-old-tokens-9999")
    assert verify_signed_email_token(token) is None


def test_admin_and_customer_tokens_do_not_cross_verify():
    customer_token = create_signed_email_token("admin")
    assert verify_admin_session_token(customer_token) is None

    admin_token = create_admin_session_token("admin", "sess-1", "csrf-1", expires_at=9999999999)
    assert verify_signed_email_token(admin_token) is None
    parsed = verify_admin_session_token(admin_token)
    assert parsed is not None
    assert parsed["sub"] == "admin"
    assert parsed["jti"] == "sess-1"
    assert parsed["csrf"] == "csrf-1"


def test_bcrypt_hash_and_invalid_hash_safety():
    hashed = hash_sensitive_data("SuperSecret!123")
    assert hashed.startswith("$2")
    assert verify_sensitive_data("SuperSecret!123", hashed) is True
    assert verify_sensitive_data("wrong", hashed) is False
    assert verify_sensitive_data("SuperSecret!123", "not-a-bcrypt-hash") is False


def test_is_admin_configured_checks_username_and_bcrypt_format(monkeypatch):
    import app.core.config as config

    assert is_admin_configured() is True

    monkeypatch.setattr(config, "ADMIN_USERNAME", "")
    assert is_admin_configured() is False

    monkeypatch.setattr(config, "ADMIN_USERNAME", "admin")
    monkeypatch.setattr(config, "ADMIN_PASSWORD_HASH", "plaintext-password")
    assert is_admin_configured() is False
