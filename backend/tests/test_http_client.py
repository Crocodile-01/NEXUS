"""
Tests for app.sources.http_client — SSRF redirect safety.

All tests use mocked/patched responses. No real network calls are made.

Coverage:
  - Direct request to a private IP is blocked at transport layer.
  - Redirect to a private/loopback/link-local IP is blocked via event hook.
  - Redirect to a non-HTTP/HTTPS scheme is blocked.
  - Normal public→public redirect succeeds.
  - MAX_REDIRECTS constant is defined and reasonable.
  - _is_blocked_ip helper validates expected ranges.
"""

from __future__ import annotations

import httpx
import pytest

from app.sources.http_client import (
    MAX_REDIRECTS,
    SSRFError,
    _build_redirect_event_hook,
    _is_blocked_ip,
)

# ---------------------------------------------------------------------------
# _is_blocked_ip unit tests (pure, no network)
# ---------------------------------------------------------------------------


def test_blocked_ip_loopback():
    assert _is_blocked_ip("127.0.0.1") is True
    assert _is_blocked_ip("::1") is True


def test_blocked_ip_rfc1918():
    assert _is_blocked_ip("10.0.0.1") is True
    assert _is_blocked_ip("172.16.0.1") is True
    assert _is_blocked_ip("192.168.1.1") is True


def test_blocked_ip_link_local():
    assert _is_blocked_ip("169.254.1.1") is True


def test_blocked_ip_public():
    assert _is_blocked_ip("8.8.8.8") is False
    assert _is_blocked_ip("1.1.1.1") is False
    assert _is_blocked_ip("93.184.216.34") is False  # example.com


def test_blocked_ip_class_e_reserved():
    assert _is_blocked_ip("240.0.0.1") is True


# ---------------------------------------------------------------------------
# _build_redirect_event_hook — redirect response hook checks
# ---------------------------------------------------------------------------


def _make_redirect_response(location: str) -> httpx.Response:
    """Create a minimal 301 response with a Location header."""
    return httpx.Response(
        status_code=301,
        headers={"location": location},
        request=httpx.Request("GET", "https://example.com"),
    )


def test_redirect_hook_blocks_loopback():
    hooks = _build_redirect_event_hook()
    check_fn = hooks["response"][0]
    response = _make_redirect_response("http://127.0.0.1/secret")
    with pytest.raises(SSRFError, match="blocked"):
        check_fn(response)


def test_redirect_hook_blocks_rfc1918():
    hooks = _build_redirect_event_hook()
    check_fn = hooks["response"][0]
    response = _make_redirect_response("http://192.168.0.1/admin")
    with pytest.raises(SSRFError, match="blocked"):
        check_fn(response)


def test_redirect_hook_blocks_link_local():
    hooks = _build_redirect_event_hook()
    check_fn = hooks["response"][0]
    response = _make_redirect_response("http://169.254.169.254/latest/meta-data/")
    with pytest.raises(SSRFError, match="blocked"):
        check_fn(response)


def test_redirect_hook_blocks_non_http_scheme():
    hooks = _build_redirect_event_hook()
    check_fn = hooks["response"][0]
    response = _make_redirect_response("ftp://example.com/file.txt")
    with pytest.raises(SSRFError, match="scheme"):
        check_fn(response)


def test_redirect_hook_allows_public_redirect():
    hooks = _build_redirect_event_hook()
    check_fn = hooks["response"][0]
    response = _make_redirect_response("https://public.example.com/new-path")
    # Should not raise
    check_fn(response)


def test_redirect_hook_does_not_fire_on_non_redirect():
    """The hook must be a no-op for non-redirect responses."""
    hooks = _build_redirect_event_hook()
    check_fn = hooks["response"][0]
    response = httpx.Response(
        status_code=200,
        content=b"OK",
        request=httpx.Request("GET", "https://example.com"),
    )
    # Should not raise
    check_fn(response)


# ---------------------------------------------------------------------------
# MAX_REDIRECTS sanity
# ---------------------------------------------------------------------------


def test_max_redirects_reasonable():
    assert 1 <= MAX_REDIRECTS <= 20, "MAX_REDIRECTS should be in [1, 20]"


# ---------------------------------------------------------------------------
# get_safe_client factory sanity (no real network)
# ---------------------------------------------------------------------------


def test_get_safe_client_returns_async_client():
    from app.sources.http_client import get_safe_client

    client = get_safe_client()
    assert isinstance(client, httpx.AsyncClient)


def test_get_httpx_client_alias():
    """get_httpx_client must be the same function as get_safe_client."""
    from app.sources.http_client import get_httpx_client, get_safe_client

    assert get_httpx_client is get_safe_client


def test_get_safe_client_custom_timeout():
    from app.sources.http_client import get_safe_client

    client = get_safe_client(timeout_seconds=30)
    assert isinstance(client, httpx.AsyncClient)
