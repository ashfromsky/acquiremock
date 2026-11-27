import pytest
from httpx import AsyncClient

from app.core.currency import format_minor_amount, get_currency_decimals
from app.models.main_models import Payment, PaymentStatus


@pytest.mark.parametrize(
    "amount,code,symbol,expected",
    [
        (25000, "USD", "$", "$250.00"),
        (50, "USD", "$", "$0.50"),
        (1000000, "EUR", "€", "€10,000.00"),
        (25000, "UAH", "₴", "250.00 ₴"),
        (500, "JPY", "¥", "¥500"),
        (15000, "KRW", "₩", "₩15,000"),
        (12345, "KWD", "KWD", "12.345 KWD"),
        (5, "BHD", "BHD", "0.005 BHD"),
        (-1050, "USD", "$", "-$10.50"),
    ],
)
def test_format_minor_amount_currencies(amount: int, code: str, symbol: str, expected: str):
    assert format_minor_amount(amount, code, symbol) == expected


def test_get_currency_decimals():
    assert get_currency_decimals("USD") == 2
    assert get_currency_decimals("jpy") == 0
    assert get_currency_decimals("KWD") == 3


async def test_checkout_and_success_render_minor_unit_amounts(client: AsyncClient, db_session):
    pending = Payment(
        id="pay-cur-1",
        amount=25000,
        reference="ORD-CUR-1",
        webhook_url="https://example.com/hook",
        redirect_url="https://example.com/ok",
        status=PaymentStatus.PENDING.value,
    )
    paid = Payment(
        id="pay-cur-2",
        amount=25000,
        reference="ORD-CUR-2",
        webhook_url="https://example.com/hook",
        redirect_url="https://example.com/ok",
        status=PaymentStatus.PAID.value,
        card_mask="**** 4444",
    )
    db_session.add(pending)
    db_session.add(paid)
    await db_session.commit()

    checkout_resp = await client.get("/checkout/pay-cur-1")
    assert checkout_resp.status_code == 200
    assert "$250.00" in checkout_resp.text
    assert "25000 $" not in checkout_resp.text

    success_resp = await client.get("/success/pay-cur-2")
    assert success_resp.status_code == 200
    assert "$250.00" in success_resp.text
