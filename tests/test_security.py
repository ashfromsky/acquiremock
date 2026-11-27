import pytest
from httpx import AsyncClient

from app.api.routes import auth as auth_routes
from app.models.main_models import Payment, SavedCard
from app.security.crypto import create_signed_email_token, hash_sensitive_data


async def test_user_info_requires_signed_session(client: AsyncClient):
    unauth = await client.get("/api/user-info")
    assert unauth.status_code == 401

    token = create_signed_email_token("alice@example.com")
    client.cookies.set("user_session", token)

    forbidden = await client.get("/api/user-info", params={"email": "bob@example.com"})
    assert forbidden.status_code == 403

    allowed = await client.get("/api/user-info")
    assert allowed.status_code == 200
    assert allowed.json() == {"operations": [], "cards": []}


async def test_auth_code_sets_cookie_and_locks_after_attempts(client: AsyncClient):
    auth_routes.login_store.clear()

    send_resp = await client.post("/api/auth/send-code", json={"email": "user@example.com"})
    assert send_resp.status_code == 200
    code = auth_routes.login_store["user@example.com"]["code"]

    for attempt in range(4):
        bad = await client.post(
            "/api/auth/verify-code",
            json={"email": "user@example.com", "code": "0000" if code != "0000" else "9999"},
        )
        assert bad.status_code == 400

    locked = await client.post(
        "/api/auth/verify-code",
        json={"email": "user@example.com", "code": "0000" if code != "0000" else "9999"},
    )
    assert locked.status_code == 429
    assert "user@example.com" not in auth_routes.login_store

    await client.post("/api/auth/send-code", json={"email": "user@example.com"})
    fresh_code = auth_routes.login_store["user@example.com"]["code"]
    ok = await client.post(
        "/api/auth/verify-code",
        json={"email": "user@example.com", "code": fresh_code},
    )
    assert ok.status_code == 200
    assert "user_session" in ok.cookies

    logout = await client.post("/api/auth/logout")
    assert logout.status_code == 200


async def test_saved_card_idor_blocked(client: AsyncClient, db_session):
    alice_card = SavedCard(
        email="alice@example.com",
        card_token="tok-alice",
        card_hash=hash_sensitive_data("4444444444444444"),
        cvv_hash="",
        expiry="12/30",
        card_mask="**** 4444",
    )
    payment = Payment(
        id="pay-idor-1",
        amount=1000,
        reference="ORD-IDOR",
        webhook_url="https://example.com/hook",
        redirect_url="https://example.com/ok",
        status="pending",
    )
    db_session.add(alice_card)
    db_session.add(payment)
    await db_session.commit()
    await db_session.refresh(alice_card)

    checkout_resp = await client.get("/checkout/pay-idor-1")
    assert checkout_resp.status_code == 200
    csrf_token = checkout_resp.cookies["csrf_token"]

    client.cookies.set("user_session", create_signed_email_token("bob@example.com"))
    resp = await client.post(
        "/api/pay/pay-idor-1",
        data={
            "saved_card_id": str(alice_card.id),
            "email": "bob@example.com",
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )
    assert resp.status_code == 404
    assert resp.json()["error"] == "SAVED_CARD_NOT_FOUND"


async def test_unsigned_user_email_cookie_cannot_bypass_otp(client: AsyncClient, db_session):
    payment = Payment(
        id="pay-bypass-1",
        amount=1000,
        reference="ORD-BYPASS",
        webhook_url="https://example.com/hook",
        redirect_url="https://example.com/ok",
        status="pending",
    )
    db_session.add(payment)
    await db_session.commit()

    checkout_resp = await client.get("/checkout/pay-bypass-1")
    csrf_token = checkout_resp.cookies["csrf_token"]

    client.cookies.set("user_email", "victim@example.com")
    resp = await client.post(
        "/api/pay/pay-bypass-1",
        data={
            "card_number": "4444 4444 4444 4444",
            "expiry": "12/30",
            "cvv": "123",
            "email": "victim@example.com",
            "csrf_token": csrf_token,
        },
        follow_redirects=False,
    )
    assert resp.status_code == 303
    assert resp.headers["location"] == "/otp/pay-bypass-1"


@pytest.mark.parametrize(
    "bad_webhook,bad_redirect",
    [
        ("http://169.254.169.254/latest/meta-data/", "https://example.com/ok"),
        ("http://localhost:8000/hook", "https://example.com/ok"),
        ("file:///etc/passwd", "https://example.com/ok"),
        ("https://example.com/hook", "javascript:alert(1)"),
    ],
)
async def test_invoice_url_validation_rejects_unsafe_urls(
    client: AsyncClient,
    bad_webhook: str,
    bad_redirect: str,
):
    resp = await client.post(
        "/api/create-invoice",
        json={
            "amount": 1000,
            "reference": "ORD-SSRF",
            "webhookUrl": bad_webhook,
            "redirectUrl": bad_redirect,
        },
    )
    assert resp.status_code == 422
