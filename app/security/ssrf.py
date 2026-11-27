import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from typing import Iterable, Optional, Union
from urllib.parse import urlparse

import httpcore
import httpx

import app.core.config as config

IPAddress = Union[ipaddress.IPv4Address, ipaddress.IPv6Address]

_METADATA_HOSTS = frozenset({
    "metadata.google.internal",
    "metadata.goog",
    "instance-data",
})

_METADATA_IPS = frozenset({
    ipaddress.ip_address("169.254.169.254"),
    ipaddress.ip_address("169.254.170.2"),
    ipaddress.ip_address("100.100.100.200"),
    ipaddress.ip_address("fd00:ec2::254"),
})

_CGNAT_NETWORK = ipaddress.ip_network("100.64.0.0/10")

_LOCAL_HOSTNAMES = frozenset({
    "localhost",
    "localhost.localdomain",
    "ip6-localhost",
    "ip6-loopback",
})

_MAX_URL_LENGTH = 2048


@dataclass(frozen=True)
class ResolvedWebhookTarget:
    url: str
    scheme: str
    hostname: str
    port: int
    resolved_ips: tuple[str, ...]
    pinned_ip: str


def _has_disallowed_chars(value: str) -> bool:
    return any(ord(ch) < 32 or ord(ch) == 127 or ch.isspace() for ch in value)


def _parse_ip_literal(hostname: str) -> Optional[IPAddress]:
    try:
        return ipaddress.ip_address(hostname)
    except ValueError:
        pass

    try:
        packed = socket.inet_aton(hostname)
    except OSError:
        return None
    return ipaddress.ip_address(packed)


def is_ip_allowed(ip: IPAddress, allow_local: bool) -> bool:
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        if not is_ip_allowed(ip.ipv4_mapped, allow_local):
            return False

    if ip in _METADATA_IPS or ip.is_link_local or ip.is_multicast or ip.is_unspecified:
        return False

    if not allow_local:
        if ip.is_private or ip.is_loopback or ip.is_reserved:
            return False
        if isinstance(ip, ipaddress.IPv4Address) and ip in _CGNAT_NETWORK:
            return False

    return True


def _is_local_hostname(hostname: str) -> bool:
    return (
        hostname in _LOCAL_HOSTNAMES
        or hostname.endswith(".localhost")
        or hostname.endswith(".local")
        or hostname.endswith(".localhost.localdomain")
        or hostname.endswith(".internal")
    )


def _is_metadata_hostname(hostname: str) -> bool:
    return hostname in _METADATA_HOSTS or any(
        hostname.endswith(f".{host}") for host in _METADATA_HOSTS
    )


def validate_webhook_url(url: str, allow_local: Optional[bool] = None) -> str:
    if allow_local is None:
        allow_local = config.ALLOW_LOCAL_WEBHOOKS

    if not isinstance(url, str):
        raise ValueError("Invalid webhook URL")

    cleaned = url.strip()
    if not cleaned or len(cleaned) > _MAX_URL_LENGTH or _has_disallowed_chars(cleaned):
        raise ValueError("Invalid webhook URL format")

    parsed = urlparse(cleaned)
    scheme = parsed.scheme.lower()
    if scheme not in ("http", "https") or not parsed.netloc or not parsed.hostname:
        raise ValueError("Invalid webhook URL: must use http or https")

    if parsed.username is not None or parsed.password is not None or "@" in parsed.netloc:
        raise ValueError("Webhook URL must not contain embedded credentials")

    try:
        port = parsed.port
    except ValueError as exc:
        raise ValueError("Invalid webhook URL port") from exc

    if port is not None and not (1 <= port <= 65535):
        raise ValueError("Webhook URL port out of range")

    hostname = parsed.hostname.lower().rstrip(".")
    if not hostname:
        raise ValueError("Invalid webhook URL hostname")

    if _is_metadata_hostname(hostname):
        raise ValueError("Webhook URL host is not allowed")

    ip_literal = _parse_ip_literal(hostname)
    if ip_literal is not None:
        if not is_ip_allowed(ip_literal, allow_local):
            raise ValueError("Webhook URL IP address is not allowed")
        return cleaned

    if not allow_local and _is_local_hostname(hostname):
        raise ValueError("Local webhook URLs are not allowed")

    return cleaned


async def resolve_and_validate_webhook_target(
    url: str,
    allow_local: Optional[bool] = None,
) -> ResolvedWebhookTarget:
    if allow_local is None:
        allow_local = config.ALLOW_LOCAL_WEBHOOKS

    cleaned = validate_webhook_url(url, allow_local=allow_local)
    parsed = urlparse(cleaned)
    scheme = parsed.scheme.lower()
    hostname = (parsed.hostname or "").lower().rstrip(".")
    port = parsed.port or (443 if scheme == "https" else 80)

    ip_literal = _parse_ip_literal(hostname)
    if ip_literal is not None:
        if not is_ip_allowed(ip_literal, allow_local):
            raise ValueError("Webhook URL IP address is not allowed")
        ip_str = str(ip_literal)
        return ResolvedWebhookTarget(
            url=cleaned,
            scheme=scheme,
            hostname=hostname,
            port=port,
            resolved_ips=(ip_str,),
            pinned_ip=ip_str,
        )

    loop = asyncio.get_running_loop()
    try:
        addr_infos = await loop.getaddrinfo(
            hostname,
            port,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM,
        )
    except socket.gaierror as exc:
        raise ValueError(f"Could not resolve webhook hostname: {hostname}") from exc

    resolved: list[str] = []
    for _family, _type, _proto, _canonname, sockaddr in addr_infos:
        if not sockaddr:
            continue
        raw_ip = str(sockaddr[0]).split("%", 1)[0]
        parsed_ip = ipaddress.ip_address(raw_ip)
        if not is_ip_allowed(parsed_ip, allow_local):
            raise ValueError(f"Webhook host {hostname} resolved to forbidden IP {parsed_ip}")
        ip_str = str(parsed_ip)
        if ip_str not in resolved:
            resolved.append(ip_str)

    if not resolved:
        raise ValueError(f"Webhook host {hostname} did not resolve to any usable IP address")

    return ResolvedWebhookTarget(
        url=cleaned,
        scheme=scheme,
        hostname=hostname,
        port=port,
        resolved_ips=tuple(resolved),
        pinned_ip=resolved[0],
    )


class PinnedNetworkBackend(httpcore.AnyIOBackend):
    def __init__(self, expected_hostname: str, pinned_ip: str) -> None:
        super().__init__()
        self._expected_hostname = expected_hostname.lower().rstrip(".")
        self._pinned_ip = pinned_ip

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: Optional[float] = None,
        local_address: Optional[str] = None,
        socket_options: Optional[Iterable[object]] = None,
    ) -> httpcore.AsyncNetworkStream:
        normalized_host = host.lower().rstrip(".")
        if normalized_host != self._expected_hostname:
            raise ValueError(f"Blocked unexpected outbound connection host: {host}")
        return await super().connect_tcp(
            self._pinned_ip,
            port,
            timeout=timeout,
            local_address=local_address,
            socket_options=socket_options,
        )


def build_pinned_async_client(
    target: ResolvedWebhookTarget,
    timeout: int = 10,
) -> httpx.AsyncClient:
    transport = httpx.AsyncHTTPTransport(trust_env=False)
    ssl_context = transport._pool._ssl_context
    transport._pool = httpcore.AsyncConnectionPool(
        ssl_context=ssl_context,
        max_connections=10,
        max_keepalive_connections=0,
        network_backend=PinnedNetworkBackend(target.hostname, target.pinned_ip),
    )
    return httpx.AsyncClient(
        transport=transport,
        timeout=timeout,
        follow_redirects=False,
        trust_env=False,
    )
