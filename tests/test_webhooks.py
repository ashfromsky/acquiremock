import socket

import httpx
import pytest
from httpx import AsyncClient
from sqlmodel import select

from app.functional.main_functions import create_payment, get_payment
from app.models.main_models import Payment, WebhookLog
from app.services.webhook_service import (
    dispatch_webhook,
    generate_webhook_signature,
    serialize_webhook_payload,
    verify_webhook_signature,
)


def test_serialize_webhook_payload_compact_sorted():
    payload = {"b": 2, "a": "x/y", "c": {"z": 1, "y": 2}}
    serialized = serialize_webhook_payload(payload)
    assert serialized == '{"a":"x/y","b":2,"c":{"y":2,"z":1}}'


def test_webhook_signature_roundtrip_and_tamper():
    payload = {"payment_id": "p-1", "amount": 5000, "status": "paid"}
    signature = generate_webhook_signature(payload, secret="secret-key")
    assert verify_webhook_signature(payload, signature, secret="secret-key") is True
    assert verify_webhook_signature({**payload, "amount": 100}, signature, secret="secret-key") is False
    assert verify_webhook_signature(payload, "0" * 64, secret="secret-key") is False


async def test_verify_webhook_endpoint(client: AsyncClient):
    payload = {"payment_id": "p-1", "status": "paid", "amount": 1000}
    signature = generate_webhook_signature(payload)

    resp_valid = await client.post(
        "/webhooks/verify",
        json=payload,
        headers={"X-Signature": signature},
    )
    assert resp_valid.status_code == 200
    assert resp_valid.json() == {"valid": True}

    resp_invalid = await client.post(
        "/webhooks/verify",
        json=payload,
        headers={"X-Signature": "deadbeef"},
    )
    assert resp_invalid.status_code == 200
    assert resp_invalid.json() == {"valid": False}

    resp_missing = await client.post("/webhooks/verify", json=payload)
    assert resp_missing.status_code == 400


async def test_dispatch_webhook_success_and_failure(
    client: AsyncClient,
    db_session,
    monkeypatch,
):
    payment = Payment(
        id="pay-wh-1",
        amount=2500,
        reference="ORD-WH-1",
        webhook_url="https://merchant.example.com/webhook",
        redirect_url="https://merchant.example.com/ok",
        status="paid",
        card_mask="**** 4444",
    )
    await create_payment(db_session, payment)

    captured = {}

    async def fake_getaddrinfo(self, host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]

    async def fake_post_success(self, url, content=None, headers=None, **kwargs):
        captured["url"] = url
        captured["content"] = content
        captured["headers"] = headers
        return httpx.Response(200, text="ok")

    monkeypatch.setattr("asyncio.base_events.BaseEventLoop.getaddrinfo", fake_getaddrinfo)
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post_success)
    ok = await dispatch_webhook("pay-wh-1")
    assert ok is True
    assert captured["url"] == "https://merchant.example.com/webhook"
    assert isinstance(captured["content"], bytes)
    assert b": " not in captured["content"]
    assert captured["headers"]["X-Payment-ID"] == "pay-wh-1"
    assert len(captured["headers"]["X-Signature"]) == 64

    db_session.expire_all()
    updated = await get_payment(db_session, "pay-wh-1")
    assert updated.webhook_status == "success"
    assert updated.webhook_attempts == 1

    logs = (await db_session.execute(select(WebhookLog).where(WebhookLog.payment_id == "pay-wh-1"))).scalars().all()
    assert len(logs) == 1
    assert logs[0].success is True
    assert logs[0].response_status == 200

    async def fake_post_fail(self, url, content=None, headers=None, **kwargs):
        return httpx.Response(500, text="server error")

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post_fail)
    ok2 = await dispatch_webhook("pay-wh-1")
    assert ok2 is False

    db_session.expire_all()
    updated2 = await get_payment(db_session, "pay-wh-1")
    assert updated2.webhook_status == "failed"
    assert updated2.webhook_attempts == 2
