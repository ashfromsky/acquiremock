import asyncio
import ipaddress
import socket
from dataclasses import dataclass
from typing import Optional, Union
from urllib.parse import SplitResult, urlsplit, urlunsplit

import httpx

IPAddress = Union[ipaddress.IPv4Address, ipaddress.IPv6Address]
ALLOWED_SCHEMES = {"http", "https"}


class UnsafeOutboundURL(ValueError):
    """Raised when an outbound URL could reach a non-public destination."""


@dataclass(frozen=True)
class ValidatedDestination:
    connection_url: str
    host_header: str
    sni_hostname: str


def _parse_url(url: str) -> tuple[SplitResult, str, Optional[int], bool]:
    if not isinstance(url, str) or not url:
        raise UnsafeOutboundURL("URL must be a non-empty string")
    if any(character.isspace() or ord(character) < 32 for character in url):
        raise UnsafeOutboundURL("URL must not contain whitespace or control characters")
    if "\\" in url:
        raise UnsafeOutboundURL("URL must not contain backslashes")

    try:
        parsed = urlsplit(url)
        scheme = parsed.scheme.lower()
        hostname = parsed.hostname
        port = parsed.port
        username = parsed.username
        password = parsed.password
    except (TypeError, ValueError) as exc:
        raise UnsafeOutboundURL("Malformed URL") from exc

    if scheme not in ALLOWED_SCHEMES:
        raise UnsafeOutboundURL("Only HTTP and HTTPS URLs are allowed")
    if not parsed.netloc or not hostname:
        raise UnsafeOutboundURL("URL must include a hostname")
    hostname_is_ipv6 = parsed.netloc.startswith("[")
    if ":" in hostname and not hostname_is_ipv6:
        raise UnsafeOutboundURL("IPv6 address must be enclosed in brackets")
    if username is not None or password is not None:
        raise UnsafeOutboundURL("URL credentials are not allowed")
    if "%" in hostname:
        raise UnsafeOutboundURL(
            "Encoded hostnames and IPv6 zone identifiers are not allowed"
        )

    return parsed, hostname, port, hostname_is_ipv6


def _normalize_hostname(hostname: str) -> tuple[str, Optional[IPAddress]]:
    try:
        address = ipaddress.ip_address(hostname)
        return str(address), address
    except ValueError:
        try:
            ascii_hostname = hostname.encode("idna").decode("ascii")
        except UnicodeError as exc:
            raise UnsafeOutboundURL("Hostname is not valid IDNA") from exc

        if "%" in ascii_hostname or "\\" in ascii_hostname:
            raise UnsafeOutboundURL("Hostname contains forbidden encoded characters")
        if not ascii_hostname or len(ascii_hostname) > 253:
            raise UnsafeOutboundURL("Hostname is malformed")

        try:
            address = ipaddress.ip_address(ascii_hostname)
        except ValueError:
            pass
        else:
            return str(address), address

        return ascii_hostname, None


def _is_public_address(address: IPAddress) -> bool:
    effective_address = address
    if isinstance(address, ipaddress.IPv6Address) and address.ipv4_mapped is not None:
        effective_address = address.ipv4_mapped
    return (
        effective_address.is_global
        and not effective_address.is_private
        and not effective_address.is_loopback
        and not effective_address.is_link_local
        and not effective_address.is_multicast
        and not effective_address.is_reserved
        and not effective_address.is_unspecified
        and not getattr(effective_address, "is_site_local", False)
    )


def _resolve_hostname(hostname: str, port: int) -> list[IPAddress]:
    try:
        answers = socket.getaddrinfo(
            hostname,
            port,
            family=socket.AF_UNSPEC,
            type=socket.SOCK_STREAM,
            proto=socket.IPPROTO_TCP,
        )
    except socket.gaierror as exc:
        raise UnsafeOutboundURL("Hostname could not be resolved") from exc

    addresses = []
    for family, _socktype, _proto, _canonname, sockaddr in answers:
        if family not in {socket.AF_INET, socket.AF_INET6}:
            raise UnsafeOutboundURL(
                "Hostname resolved to an unsupported address family"
            )
        try:
            address = ipaddress.ip_address(sockaddr[0])
        except ValueError as exc:
            raise UnsafeOutboundURL("Hostname resolved to an invalid address") from exc
        if address not in addresses:
            addresses.append(address)

    if not addresses:
        raise UnsafeOutboundURL("Hostname did not resolve to an IP address")
    return addresses


async def validate_outbound_url(url: str) -> ValidatedDestination:
    parsed, hostname, explicit_port, hostname_is_ipv6 = _parse_url(url)
    normalized_hostname, literal_address = _normalize_hostname(hostname)
    if hostname_is_ipv6 and not isinstance(literal_address, ipaddress.IPv6Address):
        raise UnsafeOutboundURL("Bracketed hostname must be an IPv6 address")
    port = explicit_port or (443 if parsed.scheme.lower() == "https" else 80)

    if literal_address is None:
        addresses = await asyncio.to_thread(
            _resolve_hostname, normalized_hostname, port
        )
    else:
        addresses = [literal_address]

    if any(not _is_public_address(address) for address in addresses):
        raise UnsafeOutboundURL("Destination must resolve only to public IP addresses")

    # Pin the connection to the validated answer so the HTTP stack cannot perform
    # a second DNS lookup and connect to a different, unvalidated address.
    selected_address = addresses[0]
    address_host = (
        f"[{selected_address}]"
        if selected_address.version == 6
        else str(selected_address)
    )
    connection_netloc = address_host
    if explicit_port is not None:
        connection_netloc = f"{connection_netloc}:{explicit_port}"

    host_header = normalized_hostname
    if ":" in normalized_hostname:
        host_header = f"[{normalized_hostname}]"
    if explicit_port is not None:
        host_header = f"{host_header}:{explicit_port}"

    connection_url = urlunsplit(
        (
            parsed.scheme.lower(),
            connection_netloc,
            parsed.path,
            parsed.query,
            "",
        )
    )
    return ValidatedDestination(
        connection_url=connection_url,
        host_header=host_header,
        sni_hostname=normalized_hostname,
    )


async def post_to_safe_destination(
    url: str,
    *,
    json: dict,
    headers: dict,
    timeout: int,
    transport: Optional[httpx.AsyncBaseTransport] = None,
) -> httpx.Response:
    destination = await validate_outbound_url(url)
    async with httpx.AsyncClient(
        timeout=timeout,
        follow_redirects=False,
        trust_env=False,
        transport=transport,
    ) as client:
        request = client.build_request(
            "POST",
            destination.connection_url,
            json=json,
            headers={**headers, "Host": destination.host_header},
        )
        request.extensions["sni_hostname"] = destination.sni_hostname
        return await client.send(request, follow_redirects=False)
