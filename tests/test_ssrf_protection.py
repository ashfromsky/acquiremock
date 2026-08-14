import socket

import httpx
import pytest
from sqlmodel import select

from app.api.routes import payments as payment_routes
from app.models.main_models import Payment
from app.models.invoice import CreateInvoiceRequest
from app.security.outbound_requests import (
    UnsafeOutboundURL,
    post_to_safe_destination,
    validate_outbound_url,
)
from app.security import outbound_requests
from app.services import webhook_service
from app.services.webhook_service import send_webhook_with_retry

pytestmark = pytest.mark.asyncio


@pytest.fixture
def fake_dns(monkeypatch):
    answers = {
        "localhost": ["127.0.0.1"],
        "private.test": ["10.0.0.8"],
        "metadata.test": ["169.254.169.254"],
        "mixed.test": ["93.184.216.34", "127.0.0.1"],
        "attacker.test": ["127.0.0.1"],
        "public.test": ["93.184.216.34", "2606:4700:4700::1111"],
        "xn--bcher-kva.test": ["93.184.216.34"],
        "2130706433": ["127.0.0.1"],
        "0x7f000001": ["127.0.0.1"],
        "0177.0.0.1": ["127.0.0.1"],
        "127.1": ["127.0.0.1"],
    }

    def getaddrinfo(host, port, **_kwargs):
        if host not in answers:
            raise socket.gaierror(socket.EAI_NONAME, "Name or service not known")
        results = []
        for address in answers[host]:
            if ":" in address:
                results.append(
                    (
                        socket.AF_INET6,
                        socket.SOCK_STREAM,
                        socket.IPPROTO_TCP,
                        "",
                        (address, port, 0, 0),
                    )
                )
            else:
                results.append(
                    (
                        socket.AF_INET,
                        socket.SOCK_STREAM,
                        socket.IPPROTO_TCP,
                        "",
                        (address, port),
                    )
                )
        return results

    class ImmediateAsyncio:
        @staticmethod
        async def to_thread(function, *args):
            return function(*args)

    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    monkeypatch.setattr(outbound_requests, "asyncio", ImmediateAsyncio)


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost/hook",
        "http://127.0.0.1/hook",
        "http://127.0.0.2/hook",
        "http://10.0.0.1/hook",
        "http://172.16.0.1/hook",
        "http://192.168.1.1/hook",
        "http://169.254.169.254/latest/meta-data",
        "http://0.0.0.0/hook",
        "http://100.64.0.1/hook",
        "http://198.18.0.1/hook",
        "http://192.0.2.1/hook",
        "http://224.0.0.1/hook",
        "http://240.0.0.1/hook",
        "http://127.0.0.1:8080/hook",
        "http://[::]/hook",
        "http://[::1]/hook",
        "http://[fc00::1]/hook",
        "http://[fec0::1]/hook",
        "http://[fe80::1]/hook",
        "http://[ff02::1]/hook",
        "http://[2001:db8::1]/hook",
        "http://[::ffff:127.0.0.1]/hook",
        "http://[::ffff:10.0.0.1]/hook",
        "http://[::ffff:169.254.169.254]/hook",
        "http://private.test/hook",
        "http://metadata.test/hook",
        "http://mixed.test/hook",
        "http://2130706433/hook",
        "http://0x7f000001/hook",
        "http://0177.0.0.1/hook",
        "http://127.1/hook",
        "file:///etc/passwd",
        "http:///missing-host",
        "http://user@public.test/hook",
        "http://public.test\\@127.0.0.1/hook",
        "http://%31%32%37.0.0.1/hook",
        "http://％31％32％37.0.0.1/hook",
        "http://public＼test/hook",
        "http://１２７。０。０。１/hook",
        "http://ⓛⓞⓒⓐⓛⓗⓞⓢⓣ/hook",
        "http://[fe80::1%25eth0]/hook",
        "http://public.test:99999/hook",
        "http://[public.test]/hook",
        "not a URL",
    ],
)
async def test_unsafe_destinations_never_reach_transport(url, fake_dns):
    calls = 0

    async def handler(_request):
        nonlocal calls
        calls += 1
        return httpx.Response(204)

    with pytest.raises(UnsafeOutboundURL):
        await post_to_safe_destination(
            url,
            json={},
            headers={},
            timeout=1,
            transport=httpx.MockTransport(handler),
        )

    assert calls == 0


@pytest.mark.parametrize(
    ("url", "expected_connection_url"),
    [
        ("http://93.184.216.34/hook", "http://93.184.216.34/hook"),
        ("https://93.184.216.34/hook", "https://93.184.216.34/hook"),
        ("https://[2606:4700:4700::1111]/hook", "https://[2606:4700:4700::1111]/hook"),
        ("https://[::ffff:93.184.216.34]/hook", "https://[::ffff:93.184.216.34]/hook"),
    ],
)
async def test_public_literal_destinations_are_allowed(url, expected_connection_url):
    destination = await validate_outbound_url(url)
    assert destination.connection_url == expected_connection_url


@pytest.mark.parametrize("scheme", ["http", "https"])
async def test_public_hostname_is_resolved_and_connection_is_pinned(scheme, fake_dns):
    seen_request = None

    async def handler(request):
        nonlocal seen_request
        seen_request = request
        return httpx.Response(204)

    response = await post_to_safe_destination(
        f"{scheme}://public.test:8443/webhook?event=paid",
        json={"status": "paid"},
        headers={"X-Test": "yes"},
        timeout=1,
        transport=httpx.MockTransport(handler),
    )

    assert response.status_code == 204
    assert str(seen_request.url) == (
        f"{scheme}://93.184.216.34:8443/webhook?event=paid"
    )
    assert seen_request.headers["Host"] == "public.test:8443"
    assert seen_request.extensions["sni_hostname"] == "public.test"


async def test_idna_hostname_is_normalized_before_dns_and_request(fake_dns):
    destination = await validate_outbound_url("https://b\u00fccher.test/webhook")

    assert destination.connection_url == "https://93.184.216.34/webhook"
    assert destination.host_header == "xn--bcher-kva.test"
    assert destination.sni_hostname == "xn--bcher-kva.test"


async def test_http_client_ignores_environment_and_redirects(monkeypatch):
    client_options = None
    send_options = None

    class CapturingClient:
        def __init__(self, **kwargs):
            nonlocal client_options
            client_options = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        def build_request(self, method, url, **kwargs):
            return httpx.Request(method, url, **kwargs)

        async def send(self, request, **kwargs):
            nonlocal send_options
            send_options = kwargs
            return httpx.Response(204, request=request)

    monkeypatch.setattr(outbound_requests.httpx, "AsyncClient", CapturingClient)

    response = await post_to_safe_destination(
        "https://93.184.216.34/webhook",
        json={},
        headers={},
        timeout=1,
    )

    assert response.status_code == 204
    assert client_options["trust_env"] is False
    assert client_options["follow_redirects"] is False
    assert send_options["follow_redirects"] is False


@pytest.mark.parametrize(
    "location",
    [
        "http://169.254.169.254/latest/meta-data",
        "http://127.0.0.1/",
        "http://10.0.0.1/",
        "https://public.test/next",
    ],
)
async def test_redirects_are_not_followed(location, fake_dns):
    seen_urls = []

    async def handler(request):
        seen_urls.append(str(request.url))
        return httpx.Response(302, headers={"Location": location})

    response = await post_to_safe_destination(
        "https://public.test/webhook",
        json={},
        headers={},
        timeout=1,
        transport=httpx.MockTransport(handler),
    )

    assert response.status_code == 302
    assert seen_urls == ["https://93.184.216.34/webhook"]


async def test_unauthenticated_webhook_url_cannot_reach_transport(
    monkeypatch, fake_dns
):
    captured_payment = None
    captured_log = None
    resolution_count = 0

    def rebinding_getaddrinfo(host, port, **_kwargs):
        nonlocal resolution_count
        assert host == "rebind.test"
        resolution_count += 1
        address = "93.184.216.34" if resolution_count == 1 else "127.0.0.1"
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                (address, port),
            )
        ]

    async def capture_payment(_db, payment):
        nonlocal captured_payment
        captured_payment = payment
        return payment

    async def capture_log(_db, webhook_log):
        nonlocal captured_log
        captured_log = webhook_log
        return webhook_log

    async def no_op(*_args):
        return None

    monkeypatch.setattr(payment_routes, "create_payment", capture_payment)
    monkeypatch.setattr(webhook_service, "log_webhook", capture_log)
    monkeypatch.setattr(webhook_service, "update_payment", no_op)
    monkeypatch.setattr(socket, "getaddrinfo", rebinding_getaddrinfo)

    invoice = CreateInvoiceRequest(
        amount=5000,
        reference="SSRF-REGRESSION",
        webhookUrl="https://rebind.test/webhook",
        redirectUrl="https://example.com/success",
    )
    await payment_routes.create_invoice(invoice, db=object())

    client_calls = 0

    def fail_if_client_is_created(*_args, **_kwargs):
        nonlocal client_calls
        client_calls += 1
        raise AssertionError("unsafe destination reached the HTTP client")

    monkeypatch.setattr(
        outbound_requests.httpx, "AsyncClient", fail_if_client_is_created
    )

    delivered = await send_webhook_with_retry(
        captured_payment,
        object(),
        timeout=1,
    )

    assert delivered is False
    assert resolution_count == 2
    assert client_calls == 0
    assert captured_payment.webhook_status == "failed"
    assert captured_log.error_message == "UNSAFE_WEBHOOK_URL"


@pytest.mark.parametrize(
    ("delivery_error", "expected_error"),
    [
        (httpx.TimeoutException("timeout"), "Request timeout"),
        (httpx.ConnectError("connection failed"), "Connection failure"),
        (httpx.ReadError("response read failed"), "HTTP request failure"),
        (RuntimeError("sensitive internal detail"), "Unexpected webhook error"),
    ],
)
async def test_webhook_delivery_failures_have_distinct_error_categories(
    delivery_error, expected_error, monkeypatch
):
    captured_log = None

    async def fail_delivery(*_args, **_kwargs):
        raise delivery_error

    async def capture_log(_db, webhook_log):
        nonlocal captured_log
        captured_log = webhook_log
        return webhook_log

    async def no_op(*_args):
        return None

    monkeypatch.setattr(webhook_service, "post_to_safe_destination", fail_delivery)
    monkeypatch.setattr(webhook_service, "log_webhook", capture_log)
    monkeypatch.setattr(webhook_service, "update_payment", no_op)

    payment = Payment(
        id="failure-categories",
        amount=5000,
        reference="FAILURE-CATEGORIES",
        webhook_url="https://93.184.216.34/webhook",
        redirect_url="https://example.com/success",
        status="paid",
    )

    delivered = await send_webhook_with_retry(payment, object(), timeout=1)

    assert delivered is False
    assert payment.webhook_status == "failed"
    assert captured_log.error_message == expected_error


async def test_webhook_http_failure_records_response_status(monkeypatch):
    captured_log = None

    async def http_failure(*_args, **_kwargs):
        return httpx.Response(503, text="service unavailable")

    async def capture_log(_db, webhook_log):
        nonlocal captured_log
        captured_log = webhook_log
        return webhook_log

    async def no_op(*_args):
        return None

    monkeypatch.setattr(webhook_service, "post_to_safe_destination", http_failure)
    monkeypatch.setattr(webhook_service, "log_webhook", capture_log)
    monkeypatch.setattr(webhook_service, "update_payment", no_op)

    payment = Payment(
        id="http-failure",
        amount=5000,
        reference="HTTP-FAILURE",
        webhook_url="https://93.184.216.34/webhook",
        redirect_url="https://example.com/success",
        status="paid",
    )

    delivered = await send_webhook_with_retry(payment, object(), timeout=1)

    assert delivered is False
    assert payment.webhook_status == "failed"
    assert captured_log.response_status == 503
    assert captured_log.error_message is None


@pytest.mark.parametrize(
    "webhook_url",
    [
        "http://localhost/hook",
        "http://127.0.0.1/hook",
        "http://10.0.0.1/hook",
        "http://172.16.0.1/hook",
        "http://192.168.0.1/hook",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/hook",
        "http://[fc00::1]/hook",
        "http://[fe80::1]/hook",
        "http://attacker.test/hook",
        "http://mixed.test/hook",
    ],
)
async def test_create_invoice_rejects_unsafe_webhook_without_persisting(
    webhook_url, client, db_session, fake_dns, monkeypatch
):
    outbound_client_calls = 0

    def fail_if_outbound_client_is_created(*_args, **_kwargs):
        nonlocal outbound_client_calls
        outbound_client_calls += 1
        raise AssertionError("invoice validation reached the outbound HTTP client")

    monkeypatch.setattr(
        outbound_requests.httpx, "AsyncClient", fail_if_outbound_client_is_created
    )

    response = await client.post(
        "/api/create-invoice",
        json={
            "amount": 5000,
            "reference": "SSRF-EARLY-VALIDATION",
            "webhookUrl": webhook_url,
            "redirectUrl": "https://example.com/success",
        },
    )

    assert response.status_code == 400
    assert response.json()["error"] == "UNSAFE_WEBHOOK_URL"
    result = await db_session.execute(select(Payment))
    assert result.scalars().all() == []
    assert outbound_client_calls == 0
