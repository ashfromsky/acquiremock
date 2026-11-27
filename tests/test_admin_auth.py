import pytest
from httpx import AsyncClient

from app.security.crypto import create_signed_email_token
from tests.conftest import TEST_ADMIN_PASSWORD, TEST_ADMIN_USERNAME, login_as_admin


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/console/config"),
        ("GET", "/api/console/overview"),
        ("GET", "/api/console/payments"),
        ("GET", "/api/console/payments/pay-1"),
        ("GET", "/api/console/webhooks"),
        ("POST", "/api/console/webhooks/pay-1/retry"),
    ],
)
async def test_console_endpoints_require_admin_auth(
    client: AsyncClient,
    method: str,
    path: str,
):
    resp = await client.request(method, path)
    assert resp.status_code == 401

    client.cookies.set("user_session", create_signed_email_token("customer@example.com"))
    resp_customer = await client.request(method, path)
    assert resp_customer.status_code == 401


async def test_admin_auth_fails_closed_when_unconfigured(
    client: AsyncClient,
    monkeypatch,
):
    import app.core.config as config

    monkeypatch.setattr(config, "ADMIN_USERNAME", "")
    monkeypatch.setattr(config, "ADMIN_PASSWORD_HASH", "")

    sess = await client.get("/api/admin/session")
    assert sess.status_code == 200
    assert sess.json()["authenticated"] is False
    assert sess.json()["configured"] is False

    login = await client.post(
        "/api/admin/login",
        json={"username": "admin", "password": "any"},
    )
    assert login.status_code == 503

    console_resp = await client.get("/api/console/config")
    assert console_resp.status_code == 503


async def test_admin_login_csrf_and_logout_revocation(client: AsyncClient):
    initial = await client.get("/api/admin/session")
    assert initial.status_code == 200
    assert initial.json() == {
        "authenticated": False,
        "username": None,
        "csrf_token": None,
        "expires_at": None,
        "configured": True,
    }

    bad_login = await client.post(
        "/api/admin/login",
        json={"username": TEST_ADMIN_USERNAME, "password": "wrong-password"},
    )
    assert bad_login.status_code == 401

    csrf_token = await login_as_admin(client)
    saved_admin_cookie = client.cookies.get("admin_session")
    assert saved_admin_cookie

    authed_sess = await client.get("/api/admin/session")
    assert authed_sess.status_code == 200
    assert authed_sess.json()["authenticated"] is True
    assert authed_sess.json()["username"] == TEST_ADMIN_USERNAME
    assert authed_sess.json()["csrf_token"] == csrf_token

    cfg = await client.get("/api/console/config")
    assert cfg.status_code == 200
    cfg_body = cfg.text
    assert TEST_ADMIN_PASSWORD not in cfg_body
    assert "ADMIN_PASSWORD_HASH" not in cfg_body
    assert "WEBHOOK_SECRET" not in cfg_body
    assert "SESSION_SECRET" not in cfg_body

    no_csrf_retry = await client.post("/api/console/webhooks/nonexistent/retry")
    assert no_csrf_retry.status_code == 403
    assert no_csrf_retry.json()["error"] == "CSRF_TOKEN_MISMATCH"

    no_csrf_logout = await client.post("/api/admin/logout")
    assert no_csrf_logout.status_code == 403

    logout = await client.post(
        "/api/admin/logout",
        headers={"X-CSRF-Token": csrf_token},
    )
    assert logout.status_code == 200

    after_logout = await client.get("/api/console/overview")
    assert after_logout.status_code == 401

    client.cookies.set("admin_session", saved_admin_cookie)
    replayed = await client.get("/api/console/overview")
    assert replayed.status_code == 401
