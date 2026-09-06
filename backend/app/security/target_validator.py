"""
target_validator.py — Input validation for NEXUS investigation targets.

All public-facing API endpoints and adapter calls must validate their
target through this module before any network I/O is attempted.

The validate_target() function accepts an ExecutionScope so that
authorization context is always explicit and auditable.
"""

from __future__ import annotations

import ipaddress
import re
from urllib.parse import urlparse

from app.security.execution_scope import DEFAULT_SCOPE, ExecutionScope


def is_private_ip(ip_str: str) -> bool:
    """Return True if the IP string is private, loopback, reserved, or link-local."""
    try:
        ip = ipaddress.ip_address(ip_str.strip())
        return ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local
    except ValueError:
        return False


def validate_domain(domain: str) -> bool:
    """Return True if *domain* is a syntactically valid FQDN."""
    domain = domain.strip().lower()
    if not domain or len(domain) > 253:
        return False
    # Full alphanumeric TLD support: [a-z0-9]{2,63}
    pattern = r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9]{2,63}$"
    return bool(re.match(pattern, domain))


def validate_url(url_str: str, allow_private: bool = False) -> bool:
    """
    Validate an HTTP/HTTPS URL and check its initial hostname safety.

    NOTE: This only validates the *initial* URL.  Redirect destinations
    are checked at the HTTP transport layer via SafeRedirectTransport —
    not here.  Do not rely on this function alone for SSRF protection.
    """
    try:
        parsed = urlparse(url_str.strip())
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        if allow_private:
            return True
        if hostname in ("localhost", "127.0.0.1", "::1"):
            return False
        return not is_private_ip(hostname)
    except Exception:  # noqa: BLE001
        return False


def validate_target(
    target: str,
    target_type: str,
    scope: ExecutionScope = DEFAULT_SCOPE,
) -> bool:
    """
    Validate *target* string given its type and the active ExecutionScope.

    Parameters
    ----------
    target:
        The raw target value supplied by the user or agent.
    target_type:
        One of: domain, ip, url, company, person, organization,
        technology, project, username.
    scope:
        The active ExecutionScope.  Defaults to PASSIVE_PUBLIC.
        Private IP access is only permitted when scope.allows_private_ip()
        returns True AND the specific IP/domain is in the authorized list.

    Returns
    -------
    bool
        True if the target is valid and within the scope's safety bounds.
    """
    target = target.strip()
    if not target:
        return False

    target_type = target_type.lower()
    allow_private = scope.allows_private_ip()

    if target_type == "domain":
        return validate_domain(target)

    if target_type == "ip":
        try:
            ip = ipaddress.ip_address(target)
            if allow_private:
                return True
            return not (ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local)
        except ValueError:
            return False

    if target_type == "url":
        return validate_url(target, allow_private=allow_private)

    if target_type in ("company", "person", "organization", "technology", "project", "username"):
        return 1 <= len(target) <= 255

    return False
