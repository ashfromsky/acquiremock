import httpx
import pytest
from httpx import AsyncClient

from app.models.main_models import Payment, PaymentStatus, SavedCard, WebhookLog
from app.security.crypto import create_signed_email_token, hash_sensitive_data


async def test_console_config_and_overview(client: AsyncClient, db_session):
    p_paid = Payment(
        id="pay-ov-1",
        amount=15000,
        reference="ORD-OV-1",
        webhook_url="https://example.com/hook",
        redirect_url="https://example.com/ok",
        status=PaymentStatus.PAID,
        card_mask="**** 4444",
        otp_code="9999",
    )
    p_pending = Payment(
        id="pay-ov-2",
        amount=5000,
        reference="ORD-OV-2",
        webhook_url="https://example.com/hook",
        redirect_url="https://example.com/ok",
        status=PaymentStatus.PENDING,
    )
    db_session.add(p_paid)
    db_session.add(p_pending)
    db_session.add(
        WebhookLog(
            payment_id="pay-ov-1",
            webhook_url="https://example.com/hook",
            payload='{"payment_id":"pay-ov-1"}',
            response_status=200,
            signature="sig",
            attempt_number=1,
            success=True,
        )
    )
    await db_session.commit()

    cfg = await client.get("/api/console/config")
    assert cfg.status_code == 200
    cfg_data = cfg.json()
    assert cfg_data["version"] == "2.0.0"
    assert "currency_code" in cfg_data
    assert "smtp_enabled" in cfg_data

    ov = await client.get("/api/console/overview")
    assert ov.status_code == 200
    ov_data = ov.json()
    assert ov_data["payments"]["total"] == 2
    assert ov_data["payments"]["paid"] == 1
    assert ov_data["payments"]["pending"] == 1
    assert ov_data["payments"]["paid_volume"] == 15000
    assert ov_data["webhooks"]["total"] == 1
    assert ov_data["webhooks"]["success_rate"] == 100.0
    for item in ov_data["recent_payments"]:
        assert "otp_code" not in item


async def test_console_payments_filter_detail_and_webhook_retry(
    client: AsyncClient,
    db_session,
    monkeypatch,
):
    payment = Payment(
        id="pay-det-1",
        amount=7500,
        reference="ORD-DETAIL-1",
        webhook_url="https://merchant.example.com/hook",
        redirect_url="https://merchant.example.com/done",
        status=PaymentStatus.PAID,
        otp_code="4321",
        card_mask="**** 4444",
    )
    db_session.add(payment)
    await db_session.commit()

    listed = await client.get("/api/console/payments", params={"status": "paid", "q": "DETAIL"})
    assert listed.status_code == 200
    listed_data = listed.json()
    assert listed_data["total"] == 1
    assert listed_data["items"][0]["id"] == "pay-det-1"

    detail = await client.get("/api/console/payments/pay-det-1")
    assert detail.status_code == 200
    detail_data = detail.json()
    assert detail_data["reference"] == "ORD-DETAIL-1"
    assert "otp_code" not in detail_data
    assert detail_data["webhook_logs"] == []

    missing = await client.get("/api/console/payments/does-not-exist")
    assert missing.status_code == 404

    orig_post = httpx.AsyncClient.post

    async def fake_post(self, url, *args, **kwargs):
        if "merchant.example.com" in str(url):
            return httpx.Response(200, text="received")
        return await orig_post(self, url, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)
    retry = await client.post("/api/console/webhooks/pay-det-1/retry")
    assert retry.status_code == 200
    retry_data = retry.json()
    assert retry_data["success"] is True
    assert retry_data["webhook_attempts"] == 1
    assert retry_data["latest_log"]["response_status"] == 200

    wh_list = await client.get("/api/console/webhooks", params={"success": "true"})
    assert wh_list.status_code == 200
    assert wh_list.json()["summary"]["succeeded"] == 1


async def test_auth_session_and_delete_saved_card_idor(client: AsyncClient, db_session):
    unauth_sess = await client.get("/api/auth/session")
    assert unauth_sess.status_code == 200
    assert unauth_sess.json() == {"authenticated": False, "email": None}

    unauth_del = await client.delete("/api/user/cards/1")
    assert unauth_del.status_code == 401

    alice_card = SavedCard(
        email="alice@example.com",
        card_token="tok-a",
        card_hash=hash_sensitive_data("4444444444444444"),
        cvv_hash="",
        expiry="12/30",
        card_mask="**** 4444",
    )
    bob_card = SavedCard(
        email="bob@example.com",
        card_token="tok-b",
        card_hash=hash_sensitive_data("4444444444444444"),
        cvv_hash="",
        expiry="11/29",
        card_mask="**** 4444",
    )
    db_session.add(alice_card)
    db_session.add(bob_card)
    await db_session.commit()
    await db_session.refresh(alice_card)
    await db_session.refresh(bob_card)

    client.cookies.set("user_session", create_signed_email_token("alice@example.com"))
    authed_sess = await client.get("/api/auth/session")
    assert authed_sess.status_code == 200
    assert authed_sess.json() == {"authenticated": True, "email": "alice@example.com"}

    idor_del = await client.delete(f"/api/user/cards/{bob_card.id}")
    assert idor_del.status_code == 404

    own_del = await client.delete(f"/api/user/cards/{alice_card.id}")
    assert own_del.status_code == 200
    assert own_del.json()["status"] == "deleted"


@pytest.mark.parametrize(
    "path",
    [
        "/",
        "/test",
        "/app",
        "/app/overview",
        "/app/payments",
        "/app/testing",
        "/app/webhooks",
        "/app/settings",
        "/merchant/login",
        "/merchant/dashboard",
    ],
)
async def test_spa_routes_return_200_and_unknown_returns_404(client: AsyncClient, path: str):
    resp = await client.get(path)
    assert resp.status_code == 200
    assert "AcquireMock" in resp.text

    not_found = await client.get("/unknown-route-that-should-404")
    assert not_found.status_code == 404
