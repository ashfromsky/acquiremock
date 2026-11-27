import ipaddress
import re
from html import escape
from typing import Optional
from urllib.parse import urlparse

import app.core.config as config


def clean_input(text: str) -> str:
    if not text:
        return ""

    safe_text = escape(text)
    safe_text = re.sub(r'javascript:', '', safe_text, flags=re.IGNORECASE)
    return safe_text.strip()


def validate_redirect_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme.lower() not in ("http", "https") or not parsed.netloc:
        raise ValueError("Invalid redirect URL: must use http or https")
    return url.strip()


def validate_webhook_url(url: str, allow_local: Optional[bool] = None) -> str:
    if allow_local is None:
        allow_local = config.ALLOW_LOCAL_WEBHOOKS

    cleaned = url.strip()
    parsed = urlparse(cleaned)
    if parsed.scheme.lower() not in ("http", "https") or not parsed.hostname:
        raise ValueError("Invalid webhook URL: must use http or https")

    hostname = parsed.hostname.lower().rstrip(".")
    if hostname == "metadata.google.internal" or hostname.endswith(".metadata.google.internal"):
        raise ValueError("Webhook URL host is not allowed")

    try:
        ip = ipaddress.ip_address(hostname)
    except ValueError:
        if not allow_local and (
            hostname == "localhost"
            or hostname.endswith(".localhost")
            or hostname.endswith(".local")
        ):
            raise ValueError("Local webhook URLs are not allowed")
        return cleaned

    if ip.is_link_local or ip.is_multicast or ip.is_unspecified:
        raise ValueError("Webhook URL IP address is not allowed")

    if not allow_local and (ip.is_private or ip.is_loopback or ip.is_reserved):
        raise ValueError("Private or loopback webhook URLs are not allowed")

    return cleaned
