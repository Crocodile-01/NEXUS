from __future__ import annotations

import ipaddress
from urllib.parse import urlparse

from app.security.execution_scope import ExecutionMode, ExecutionScope
from app.security.target_validator import (
    is_private_ip,
    validate_domain,
    validate_url,
)
from app.tools.base import RegisteredTool, ToolRequest


class GuardrailViolationError(Exception):
    """Raised when a tool execution request violates safety guardrails or scope policies."""


def validate_tool_call(
    tool: RegisteredTool,
    request: ToolRequest,
    scope: ExecutionScope,
) -> None:
    """
    Central guardrail validator for all tool invocations.

    Enforces:
    1. Tool enabled status.
    2. Execution mode compatibility (PASSIVE_PUBLIC vs AUTHORIZED_SECURITY_ASSESSMENT).
    3. Target safety & syntax validation (FQDN, IP, URL).
    4. Private network / SSRF prevention under PASSIVE_PUBLIC mode.
    5. Specific target authorization when running in elevated assessment mode.
    """
    if not tool.enabled:
        raise GuardrailViolationError(f"Tool '{tool.name}' is currently disabled.")

    # 1. Execution Mode Verification
    if tool.required_execution_mode == ExecutionMode.AUTHORIZED_SECURITY_ASSESSMENT:
        if scope.mode != ExecutionMode.AUTHORIZED_SECURITY_ASSESSMENT:
            raise GuardrailViolationError(
                f"Tool '{tool.name}' requires AUTHORIZED_SECURITY_ASSESSMENT mode; active mode is '{scope.mode}'."
            )
        if not scope.is_elevated:
            raise GuardrailViolationError(
                f"Tool '{tool.name}' requires explicit target authorization list. "
                "AUTHORIZED_SECURITY_ASSESSMENT mode without authorized targets is not self-authorizing."
            )

    target = request.target.strip()
    if not target:
        raise GuardrailViolationError(f"Tool '{tool.name}' target cannot be empty.")

    # 2. Target Syntax & SSRF / Safety Validation
    target_type = request.target_type.lower()

    # Check if target is a URL
    if target_type == "url" or target.startswith(("http://", "https://")):
        parsed = urlparse(target)
        if parsed.scheme not in ("http", "https"):
            raise GuardrailViolationError(
                f"URL target '{target}' uses disallowed scheme '{parsed.scheme}'. Only HTTP and HTTPS are permitted."
            )
        if not validate_url(target, allow_private=scope.allows_private_ip()):
            raise GuardrailViolationError(
                f"URL target '{target}' resolves to localhost, loopback, or private destination. "
                "Blocked by PASSIVE_PUBLIC SSRF guardrail."
            )

    # Check if target is a domain
    elif target_type == "domain":
        if not validate_domain(target):
            raise GuardrailViolationError(f"Target '{target}' is not a valid FQDN domain name.")

    # Check if target is an IP address
    elif target_type == "ip":
        try:
            ip = ipaddress.ip_address(target)
            if not scope.allows_private_ip() and is_private_ip(target):
                raise GuardrailViolationError(
                    f"IP target '{target}' is in a private, loopback, or reserved range. "
                    "Blocked by PASSIVE_PUBLIC guardrail."
                )
        except ValueError:
            raise GuardrailViolationError(f"Target '{target}' is not a valid IP address.") from None

    # General / entity target checks
    else:
        # If target can parse as IP, verify it's not private
        try:
            ip = ipaddress.ip_address(target)
            if not scope.allows_private_ip() and (ip.is_private or ip.is_loopback or ip.is_reserved or ip.is_link_local):
                raise GuardrailViolationError(
                    f"Target '{target}' is a private IP address. Blocked under PASSIVE_PUBLIC mode."
                )
        except ValueError:
            # Not an IP string, validate general length
            if not (1 <= len(target) <= 255):
                raise GuardrailViolationError(f"Target length must be between 1 and 255 characters, got {len(target)}.")

    # 3. Target Scope Membership Check for Elevated Mode
    if scope.mode == ExecutionMode.AUTHORIZED_SECURITY_ASSESSMENT and scope.is_elevated:
        # When in elevated mode, if target is domain or IP, verify it is in authorized lists
        if target_type == "domain" and scope.authorized_domains:
            if target.lower() not in [d.lower() for d in scope.authorized_domains]:
                raise GuardrailViolationError(
                    f"Domain target '{target}' is not in authorized_domains list for this assessment."
                )
        elif target_type == "ip" and scope.authorized_ips and target not in scope.authorized_ips:
            raise GuardrailViolationError(
                f"IP target '{target}' is not in authorized_ips list for this assessment."
            )
