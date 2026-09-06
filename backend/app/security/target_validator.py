import ipaddress
import re
from urllib.parse import urlparse


def is_private_ip(ip_str: str) -> bool:
    """Check if an IP string is a private/loopback/reserved IP address."""
    try:
        ip = ipaddress.ip_address(ip_str.strip())
        return ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local
    except ValueError:
        return False


def validate_domain(domain: str) -> bool:
    """Validate standard domain name format."""
    domain = domain.strip().lower()
    if len(domain) > 253 or not domain:
        return False
    # Regex for standard FQDN
    pattern = r"^(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-2]{2,63}$"
    return bool(re.match(pattern, domain))


def validate_url(url_str: str, allow_private: bool = False) -> bool:
    """Validate HTTP/HTTPS URL and check host safety."""
    try:
        parsed = urlparse(url_str.strip())
        if parsed.scheme not in ("http", "https"):
            return False
        hostname = parsed.hostname
        if not hostname:
            return False
        return allow_private or not (hostname in ("localhost", "127.0.0.1", "::1") or is_private_ip(hostname))
    except Exception:  # noqa: BLE001
        return False


def validate_target(target: str, target_type: str, mode: str = "PASSIVE_PUBLIC") -> bool:
    """
    Validate target string based on target_type and execution mode.
    Returns True if target is valid and within safe execution bounds.
    """
    target = target.strip()
    if not target:
        return False

    target_type = target_type.lower()
    allow_private = (mode == "AUTHORIZED_SECURITY_ASSESSMENT")

    if target_type == "domain":
        return validate_domain(target)
    elif target_type == "ip":
        try:
            ip = ipaddress.ip_address(target)
            return allow_private or not (ip.is_private or ip.is_loopback or ip.is_reserved)
        except ValueError:
            return False
    elif target_type == "url":
        return validate_url(target, allow_private=allow_private)
    elif target_type in ("company", "person", "organization", "technology", "project", "username"):
        return 1 <= len(target) <= 255
    return False
