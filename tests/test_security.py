import pytest
from app.security.crypto import (
    generate_secure_otp,
    generate_csrf_token,
    hash_sensitive_data,
    verify_sensitive_data
)
from app.security.sanitizer import clean_input


def test_csrf_token_generation():
    token1 = generate_csrf_token()
    token2 = generate_csrf_token()
    assert token1 != token2
    assert len(token1) > 20


def test_otp_uniqueness():
    otps = [generate_secure_otp() for _ in range(100)]
    unique_otps = set(otps)
    assert len(unique_otps) > 50


def test_hash_different_for_same_input():
    data = "same_input"
    hash1 = hash_sensitive_data(data)
    hash2 = hash_sensitive_data(data)
    assert hash1 != hash2
    assert verify_sensitive_data(data, hash1)
    assert verify_sensitive_data(data, hash2)


def test_clean_input_removes_html():
    dirty_input = "<script>alert('xss')</script>Hello"
    cleaned = clean_input(dirty_input)
    assert "<script>" not in cleaned
    assert "Hello" in cleaned


def test_clean_input_safe_string():
    safe_input = "Normal text 123"
    cleaned = clean_input(safe_input)
    assert cleaned == safe_input