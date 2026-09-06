from app.security.target_validator import (
    is_private_ip,
    validate_domain,
    validate_target,
    validate_url,
)


def test_is_private_ip():
    assert is_private_ip("127.0.0.1") is True
    assert is_private_ip("10.0.0.1") is True
    assert is_private_ip("192.168.1.1") is True
    assert is_private_ip("8.8.8.8") is False
    assert is_private_ip("1.1.1.1") is False


def test_validate_domain():
    assert validate_domain("example.com") is True
    assert validate_domain("sub.domain.co.uk") is True
    assert validate_domain("invalid_domain!") is False
    assert validate_domain("") is False


def test_validate_url():
    assert validate_url("https://example.com/api") is True
    assert validate_url("http://1.1.1.1/info") is True
    assert validate_url("http://localhost:8000") is False  # Rejected by default (PASSIVE_PUBLIC)
    assert validate_url("http://192.168.1.5/admin") is False  # SSRF protection
    assert validate_url("ftp://example.com") is False  # Non-HTTP/HTTPS scheme


def test_validate_target():
    # Passive public mode checks
    assert validate_target("nvidia.com", "domain", "PASSIVE_PUBLIC") is True
    assert validate_target("8.8.8.8", "ip", "PASSIVE_PUBLIC") is True
    assert validate_target("127.0.0.1", "ip", "PASSIVE_PUBLIC") is False  # Blocked in passive public
    assert validate_target("NVIDIA Corporation", "company", "PASSIVE_PUBLIC") is True
    assert validate_target("", "company", "PASSIVE_PUBLIC") is False
