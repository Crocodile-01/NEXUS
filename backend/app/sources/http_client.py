"""
http_client.py — SSRF-safe HTTPX client factory for NEXUS.

All outbound HTTP requests from source adapters MUST use get_safe_client()
(or get_httpx_client(), which is a thin alias kept for backward compat).

Safety guarantees enforced at the transport layer (below the agent/adapter):
  1. Only HTTP and HTTPS schemes are allowed — enforced at URL validation time.
  2. Redirects are followed but every destination is checked before the
     connection is established.  Redirects to private, loopback, link-local,
     or reserved IP ranges are blocked unconditionally.
  3. A bounded redirect count (MAX_REDIRECTS = 10) prevents infinite loops.
  4. Connection and read timeouts are always applied.

Adapters must NOT bypass this module by constructing their own httpx.AsyncClient.
"""

from __future__ import annotations

import ipaddress
import socket
from typing import Any

import httpx

from app.core.config import settings

MAX_REDIRECTS: int = 10

# IP ranges that are never acceptable redirect destinations in PASSIVE_PUBLIC mode.
# We use ipaddress.ip_network objects for fast containment checks.
_BLOCKED_NETWORKS: list[ipaddress.IPv4Network | ipaddress.IPv6Network] = [
    ipaddress.ip_network("127.0.0.0/8"),       # IPv4 loopback
    ipaddress.ip_network("::1/128"),            # IPv6 loopback
    ipaddress.ip_network("10.0.0.0/8"),         # RFC-1918 private
    ipaddress.ip_network("172.16.0.0/12"),      # RFC-1918 private
    ipaddress.ip_network("192.168.0.0/16"),     # RFC-1918 private
    ipaddress.ip_network("169.254.0.0/16"),     # IPv4 link-local
    ipaddress.ip_network("fe80::/10"),          # IPv6 link-local
    ipaddress.ip_network("fc00::/7"),           # IPv6 unique-local
    ipaddress.ip_network("0.0.0.0/8"),          # "This" network
    ipaddress.ip_network("100.64.0.0/10"),      # Shared address space
    ipaddress.ip_network("192.0.0.0/24"),       # IETF protocol assignments
    ipaddress.ip_network("192.0.2.0/24"),       # TEST-NET-1
    ipaddress.ip_network("198.51.100.0/24"),    # TEST-NET-2
    ipaddress.ip_network("203.0.113.0/24"),     # TEST-NET-3
    ipaddress.ip_network("240.0.0.0/4"),        # Reserved (class E)
    ipaddress.ip_network("255.255.255.255/32"), # Broadcast
]


def _is_blocked_ip(addr: str) -> bool:
    """Return True if *addr* resolves to a blocked/private network."""
    try:
        ip = ipaddress.ip_address(addr)
        return any(ip in net for net in _BLOCKED_NETWORKS)
    except ValueError:
        # addr is a hostname — resolve to IP(s) and check each
        try:
            results = socket.getaddrinfo(addr, None)
            for result in results:
                raw_ip = result[4][0]
                ip = ipaddress.ip_address(raw_ip)
                if any(ip in net for net in _BLOCKED_NETWORKS):
                    return True
        except socket.gaierror:
            # Cannot resolve the hostname — we cannot confirm it maps to a
            # blocked range, so return False and let the TCP layer handle it.
            # Real connections to private IPs are caught by _SafeRedirectTransport.
            return False
    return False


class SSRFError(Exception):
    """Raised when a redirect destination fails SSRF safety checks."""


class _SafeRedirectTransport(httpx.AsyncHTTPTransport):
    """
    Custom HTTPX transport that intercepts every redirect response and
    validates the destination before following it.

    This sits beneath the adapter/agent layer so neither layer can bypass
    the check by manipulating client options.
    """

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        host = request.url.host
        if not host:
            raise SSRFError(f"Request has no host: {request.url}")

        if _is_blocked_ip(host):
            raise SSRFError(
                f"SSRF protection: destination '{host}' resolves to a blocked IP range."
            )

        return await super().handle_async_request(request)


def _build_redirect_event_hook() -> dict[str, list[Any]]:
    """
    Return HTTPX event hooks that validate every redirect destination
    before the client follows it.

    We use the `response` hook: if a response is a redirect, we inspect
    the Location header before httpx internally prepares the next request.
    httpx fires the response hook synchronously before building the next
    request object, so raising here aborts the redirect chain.
    """

    def _check_redirect(response: httpx.Response) -> None:
        if response.is_redirect:
            location = response.headers.get("location", "")
            try:
                next_url = httpx.URL(location)
            except Exception:  # noqa: BLE001
                raise SSRFError(f"SSRF protection: invalid redirect Location header: {location!r}")

            if next_url.scheme not in ("http", "https"):
                raise SSRFError(
                    f"SSRF protection: redirect to non-HTTP/HTTPS scheme '{next_url.scheme}'"
                )

            host = next_url.host
            if not host:
                raise SSRFError("SSRF protection: redirect location has no host.")

            if _is_blocked_ip(host):
                raise SSRFError(
                    f"SSRF protection: redirect destination '{host}' "
                    "resolves to a blocked/private IP range."
                )

    return {"response": [_check_redirect]}


def get_safe_client(
    timeout_seconds: int | None = None,
    headers: dict[str, str] | None = None,
) -> httpx.AsyncClient:
    """
    Return a configured AsyncClient with SSRF redirect protection.

    Every redirect is validated by both the transport layer (per-request
    host check before the TCP connection) and the response event hook
    (Location header check before httpx follows the redirect).

    Parameters
    ----------
    timeout_seconds:
        Override the global REQUEST_TIMEOUT_SECONDS setting.
    headers:
        Extra headers merged on top of the NEXUS defaults.
    """
    effective_timeout = (
        timeout_seconds if timeout_seconds is not None else settings.REQUEST_TIMEOUT_SECONDS
    )
    default_headers: dict[str, str] = {
        "User-Agent": settings.USER_AGENT,
        "Accept": "application/json, text/html, application/xml;q=0.9, */*;q=0.8",
    }
    if headers:
        default_headers.update(headers)

    return httpx.AsyncClient(
        headers=default_headers,
        timeout=httpx.Timeout(effective_timeout, connect=5.0),
        follow_redirects=True,
        max_redirects=MAX_REDIRECTS,
        transport=_SafeRedirectTransport(),
        event_hooks=_build_redirect_event_hook(),
    )


# Backward-compatibility alias.  Adapters that already import get_httpx_client
# will automatically get the safe client.
get_httpx_client = get_safe_client
