"""
Tests for app.security.target_validator and app.security.execution_scope.

Covers:
  - Domain regex regression (TLD bug fix: [a-z0-9] not [a-z0-2])
  - URL validation (scheme, private IP, localhost)
  - IP validation (private vs public)
  - validate_target() with ExecutionScope
  - ExecutionScope model invariants
"""


from app.security.execution_scope import ExecutionMode, ExecutionScope
from app.security.target_validator import (
    is_private_ip,
    validate_domain,
    validate_target,
    validate_url,
)

# ---------------------------------------------------------------------------
# is_private_ip
# ---------------------------------------------------------------------------


def test_is_private_ip_loopback():
    assert is_private_ip("127.0.0.1") is True


def test_is_private_ip_rfc1918():
    assert is_private_ip("10.0.0.1") is True
    assert is_private_ip("192.168.1.1") is True
    assert is_private_ip("172.16.0.0") is True


def test_is_private_ip_public():
    assert is_private_ip("8.8.8.8") is False
    assert is_private_ip("1.1.1.1") is False


# ---------------------------------------------------------------------------
# validate_domain — regression tests for the TLD regex bug fix
# ---------------------------------------------------------------------------


def test_validate_domain_standard():
    assert validate_domain("example.com") is True
    assert validate_domain("sub.domain.co.uk") is True


def test_validate_domain_numeric_tld():
    """TLDs with digits (e.g. .s3, .io, .ai) must be accepted (regression: [a-z0-2] bug)."""
    assert validate_domain("bucket.s3") is True          # digit in TLD
    assert validate_domain("example.io") is True          # common TLD
    assert validate_domain("model.ai") is True            # common TLD
    assert validate_domain("cdn.mp4") is True             # all-digit TLD portion
    assert validate_domain("www.example.c3") is True      # digit 3 in TLD


def test_validate_domain_all_digit_tld_boundary():
    """Digits 3-9 were previously blocked by the [a-z0-2] bug."""
    assert validate_domain("host.t3") is True             # digit 3
    assert validate_domain("host.t5") is True             # digit 5
    assert validate_domain("host.t9") is True             # digit 9


def test_validate_domain_invalid():
    assert validate_domain("invalid_domain!") is False
    assert validate_domain("") is False
    assert validate_domain("no-tld") is False
    assert validate_domain("-starts-with-dash.com") is False


def test_validate_domain_length():
    # > 253 chars should be rejected
    long_domain = "a" * 250 + ".com"
    assert validate_domain(long_domain) is False


# ---------------------------------------------------------------------------
# validate_url
# ---------------------------------------------------------------------------


def test_validate_url_public_https():
    assert validate_url("https://example.com/api") is True


def test_validate_url_public_http():
    assert validate_url("http://1.1.1.1/info") is True


def test_validate_url_localhost_blocked():
    assert validate_url("http://localhost:8000") is False


def test_validate_url_private_ip_blocked():
    assert validate_url("http://192.168.1.5/admin") is False


def test_validate_url_loopback_blocked():
    assert validate_url("http://127.0.0.1/secret") is False


def test_validate_url_non_http_scheme():
    assert validate_url("ftp://example.com") is False


def test_validate_url_allow_private():
    """allow_private=True is only ever passed when scope.allows_private_ip() is True."""
    assert validate_url("http://192.168.1.5/admin", allow_private=True) is True
    assert validate_url("http://localhost:8000", allow_private=True) is True


# ---------------------------------------------------------------------------
# validate_target with ExecutionScope
# ---------------------------------------------------------------------------


def test_validate_target_passive_domain():
    scope = ExecutionScope.passive_public()
    assert validate_target("nvidia.com", "domain", scope) is True


def test_validate_target_passive_numeric_tld():
    """Regression: 'nvidia.s3' should be valid (digit in TLD)."""
    scope = ExecutionScope.passive_public()
    assert validate_target("bucket.s3", "domain", scope) is True


def test_validate_target_passive_ip_public():
    scope = ExecutionScope.passive_public()
    assert validate_target("8.8.8.8", "ip", scope) is True


def test_validate_target_passive_ip_private_blocked():
    scope = ExecutionScope.passive_public()
    assert validate_target("127.0.0.1", "ip", scope) is False
    assert validate_target("192.168.1.1", "ip", scope) is False


def test_validate_target_passive_company():
    scope = ExecutionScope.passive_public()
    assert validate_target("NVIDIA Corporation", "company", scope) is True
    assert validate_target("", "company", scope) is False


def test_validate_target_elevated_allows_private_ip():
    """An elevated scope with an authorized IP permits that private IP target."""
    scope = ExecutionScope(
        mode=ExecutionMode.AUTHORIZED_SECURITY_ASSESSMENT,
        authorized_ips=["192.168.1.1"],
        authorized_by="user:test",
    )
    assert scope.allows_private_ip() is True
    assert validate_target("192.168.1.1", "ip", scope) is True


def test_validate_target_default_scope_used():
    """validate_target defaults to PASSIVE_PUBLIC when no scope is supplied."""
    # Private IP should be blocked with the default scope
    assert validate_target("127.0.0.1", "ip") is False


# ---------------------------------------------------------------------------
# ExecutionScope invariants
# ---------------------------------------------------------------------------


def test_execution_scope_passive_public_defaults():
    scope = ExecutionScope.passive_public()
    assert scope.is_passive_public is True
    assert scope.is_elevated is False
    assert scope.allows_private_ip() is False


def test_execution_scope_mode_string_is_not_elevated():
    """AUTHORIZED_SECURITY_ASSESSMENT mode without authorized domains/IPs is NOT elevated."""
    scope = ExecutionScope(mode=ExecutionMode.AUTHORIZED_SECURITY_ASSESSMENT)
    assert scope.is_elevated is False
    assert scope.allows_private_ip() is False


def test_execution_scope_elevated_requires_authorized_list():
    scope = ExecutionScope(
        mode=ExecutionMode.AUTHORIZED_SECURITY_ASSESSMENT,
        authorized_domains=["target.example.com"],
        authorized_by="user:admin",
    )
    assert scope.is_elevated is True
    assert scope.allows_private_ip() is True
