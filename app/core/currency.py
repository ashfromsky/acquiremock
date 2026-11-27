from typing import Optional

import app.core.config as config

ZERO_DECIMAL_CURRENCIES = frozenset({
    "BIF",
    "CLP",
    "DJF",
    "GNF",
    "ISK",
    "JPY",
    "KMF",
    "KRW",
    "PYG",
    "RWF",
    "UGX",
    "VND",
    "VUV",
    "XAF",
    "XOF",
    "XPF",
})

THREE_DECIMAL_CURRENCIES = frozenset({
    "BHD",
    "IQD",
    "JOD",
    "KWD",
    "LYD",
    "OMR",
    "TND",
})

PREFIX_SYMBOLS = frozenset({"$", "£", "€", "¥", "₹", "₩", "₪", "₫"})


def get_currency_decimals(currency_code: Optional[str] = None) -> int:
    code = (currency_code or config.CURRENCY_CODE).strip().upper()
    if code in ZERO_DECIMAL_CURRENCIES:
        return 0
    if code in THREE_DECIMAL_CURRENCIES:
        return 3
    return 2


def format_minor_amount(
    amount_minor: int,
    currency_code: Optional[str] = None,
    currency_symbol: Optional[str] = None,
) -> str:
    code = (currency_code or config.CURRENCY_CODE).strip().upper()
    symbol = config.CURRENCY_SYMBOL if currency_symbol is None else currency_symbol
    decimals = get_currency_decimals(code)

    value = int(amount_minor)
    negative = value < 0
    abs_value = abs(value)

    if decimals == 0:
        number_str = f"{abs_value:,}"
    else:
        divisor = 10 ** decimals
        whole, frac = divmod(abs_value, divisor)
        number_str = f"{whole:,}.{frac:0{decimals}d}"

    sign = "-" if negative else ""
    if symbol in PREFIX_SYMBOLS:
        return f"{sign}{symbol}{number_str}"
    return f"{sign}{number_str} {symbol}".strip()
