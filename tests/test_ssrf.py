import socket

import httpx
import pytest
from sqlmodel import select

import app.core.config as config
from app.functional.main_functions import create_payment
from app.models.main_models import Payment, WebhookLog
from app.security.ssrf import (
    PinnedNetworkBackend,
    resolve_and_validate_webhook_target,
    validate_webhook_url,
)
from app.services.webhook_service import dispatch_webhook


def test_allow_local_webhooks_defaults_to_false():
    assert config.ALLOW_LOCAL_WEBHOOKS is False


@pytest.mark.parametrize(
    "bad_url",
    [
        "",
        "   ",
        "not-a-url",
        "ftp://example.com/hook",
        "file:///etc/passwd",
        "javascript:alert(1)",
        "https://user:pass@example.com/hook",
        "https://user@example.com/hook",
        "https://example.com:99999/hook",
        "http://10.0.0.1/hook",
        "http://172.16.0.1/hook",
        "http://192.168.1.10/hook",
        "http://100.64.0.1/hook",
        "http://127.0.0.1:8080/hook",
        "http://2130706433/hook",
        "http://0x7f000001/hook",
        "http://[::1]:8080/hook",
        "http://[fc00::1]/hook",
        "http://[fd12:3456::1]/hook",
        "http://[::ffff:127.0.0.1]/hook",
        "http://[::ffff:169.254.169.254]/latest/meta-data/",
        "http://169.254.169.254/latest/meta-data/",
        "http://169.254.170.2/v2/credentials",
        "http://100.100.100.200/latest/meta-data/",
        "http://[fd00:ec2::254]/latest/meta-data/",
        "http://metadata.google.internal/computeMetadata/v1/",
        "http://sub.metadata.google.internal/",
        "http://localhost/hook",
        "http://api.localhost/hook",
        "http://service.local/hook",
        "http://0.0.0.0/hook",
        "http://224.0.0.1/hook",
    ],
)
def test_validate_webhook_url_blocks_unsafe_targets(bad_url: str):
    with pytest.raises(ValueError):
        validate_webhook_url(bad_url, allow_local=False)


@pytest.mark.parametrize(
    "metadata_url",
    [
        "http://169.254.169.254/latest/meta-data/",
        "http://metadata.google.internal/computeMetadata/v1/",
        "http://[::ffff:169.254.169.254]/latest/meta-data/",
        "http://[fd00:ec2::254]/latest/meta-data/",
    ],
)
def test_metadata_targets_blocked_even_when_allow_local_enabled(metadata_url: str):
    with pytest.raises(ValueError):
        validate_webhook_url(metadata_url, allow_local=True)


@pytest.mark.parametrize(
    "dns_ips",
    [
        ["10.10.0.5"],
        ["127.0.0.1"],
        ["::1"],
        ["fc00::5"],
        ["169.254.169.254"],
        ["93.184.216.34", "192.168.1.50"],
        ["93.184.216.34", "fe80::1"],
    ],
)
async def test_dns_resolution_rejects_private_and_mixed_records(monkeypatch, dns_ips: list[str]):
    async def fake_getaddrinfo(self, host, port, *args, **kwargs):
        results = []
        for ip_str in dns_ips:
            family = socket.AF_INET6 if ":" in ip_str else socket.AF_INET
            sockaddr = (ip_str, port, 0, 0) if family == socket.AF_INET6 else (ip_str, port)
            results.append((family, socket.SOCK_STREAM, 6, "", sockaddr))
        return results

    monkeypatch.setattr("asyncio.base_events.BaseEventLoop.getaddrinfo", fake_getaddrinfo)

    with pytest.raises(ValueError):
        await resolve_and_validate_webhook_target("https://evil.example.com/hook", allow_local=False)


async def test_dns_resolution_allows_public_records(monkeypatch):
    async def fake_getaddrinfo(self, host, port, *args, **kwargs):
        return [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port)),
            (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("2606:2800:220:1:248:1893:25c8:1946", port, 0, 0)),
        ]

    monkeypatch.setattr("asyncio.base_events.BaseEventLoop.getaddrinfo", fake_getaddrinfo)

    target = await resolve_and_validate_webhook_target("https://public.example.com/hook", allow_local=False)
    assert target.hostname == "public.example.com"
    assert target.pinned_ip == "93.184.216.34"
    assert len(target.resolved_ips) == 2


async def test_pinned_network_backend_prevents_dns_rebinding(monkeypatch):
    dialed = {}

    async def fake_super_connect_tcp(self, host, port, **kwargs):
        dialed["host"] = host
        dialed["port"] = port
        return object()

    monkeypatch.setattr("httpcore.AnyIOBackend.connect_tcp", fake_super_connect_tcp)

    backend = PinnedNetworkBackend("rebind.example.com", "93.184.216.34")
    await backend.connect_tcp("rebind.example.com", 443)
    assert dialed == {"host": "93.184.216.34", "port": 443}

    with pytest.raises(ValueError):
        await backend.connect_tcp("169.254.169.254", 80)


async def test_redirect_ssrf_is_not_followed_and_recorded_as_failure(db_session, monkeypatch):
    payment = Payment(
        id="pay-ssrf-redir",
        amount=5000,
        reference="ORD-SSRF-REDIR",
        webhook_url="https://redirector.example.com/hook",
        redirect_url="https://redirector.example.com/done",
        status="paid",
        card_mask="**** 4444",
    )
    await create_payment(db_session, payment)

    async def fake_getaddrinfo(self, host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port))]

    called_urls = []

    async def fake_post(self, url, **kwargs):
        called_urls.append(str(url))
        assert kwargs.get("follow_redirects", self.follow_redirects) is False
        return httpx.Response(
            302,
            headers={"Location": "http://169.254.169.254/latest/meta-data/"},
        )

    monkeypatch.setattr("asyncio.base_events.BaseEventLoop.getaddrinfo", fake_getaddrinfo)
    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    ok = await dispatch_webhook("pay-ssrf-redir")
    assert ok is False
    assert called_urls == ["https://redirector.example.com/hook"]

    logs = (
        await db_session.execute(select(WebhookLog).where(WebhookLog.payment_id == "pay-ssrf-redir"))
    ).scalars().all()
    assert len(logs) == 1
    assert logs[0].success is False
    assert logs[0].response_status == 302
    assert "Redirect" in (logs[0].error_message or "")


async def test_dispatch_webhook_revalidates_dns_before_delivery(db_session, monkeypatch):
    payment = Payment(
        id="pay-ssrf-rebind",
        amount=5000,
        reference="ORD-SSRF-REBIND",
        webhook_url="https://rebinding.example.com/hook",
        redirect_url="https://rebinding.example.com/done",
        status="paid",
        card_mask="**** 4444",
    )
    await create_payment(db_session, payment)

    async def fake_getaddrinfo(self, host, port, *args, **kwargs):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port))]

    monkeypatch.setattr("asyncio.base_events.BaseEventLoop.getaddrinfo", fake_getaddrinfo)

    ok = await dispatch_webhook("pay-ssrf-rebind")
    assert ok is False

    logs = (
        await db_session.execute(select(WebhookLog).where(WebhookLog.payment_id == "pay-ssrf-rebind"))
    ).scalars().all()
    assert len(logs) == 1
    assert logs[0].success is False
    assert "forbidden IP" in (logs[0].error_message or "")
