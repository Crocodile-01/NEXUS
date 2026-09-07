from __future__ import annotations

import pytest

from app.guardrails.tool_guardrails import GuardrailViolationError, validate_tool_call
from app.security.execution_scope import ExecutionMode, ExecutionScope
from app.tools.base import RegisteredTool, ToolRequest, ToolResult


async def _dummy_func(request: ToolRequest) -> ToolResult:
    return ToolResult(
        success=True,
        tool_name="test_tool",
        target=request.target,
    )


def test_disabled_tool_rejection():
    tool = RegisteredTool(
        name="disabled_tool",
        description="Disabled",
        category="test",
        func=_dummy_func,
        enabled=False,
    )
    req = ToolRequest(target="example.com", target_type="domain")
    with pytest.raises(GuardrailViolationError, match="currently disabled"):
        validate_tool_call(tool=tool, request=req, scope=ExecutionScope.passive_public())


def test_passive_public_blocks_private_ip():
    tool = RegisteredTool(
        name="ip_tool",
        description="IP check",
        category="test",
        func=_dummy_func,
    )
    # Loopback
    with pytest.raises(GuardrailViolationError, match="private, loopback, or reserved"):
        validate_tool_call(tool=tool, request=ToolRequest(target="127.0.0.1", target_type="ip"), scope=ExecutionScope.passive_public())
    # RFC 1918
    with pytest.raises(GuardrailViolationError, match="private, loopback, or reserved"):
        validate_tool_call(tool=tool, request=ToolRequest(target="192.168.1.1", target_type="ip"), scope=ExecutionScope.passive_public())
    with pytest.raises(GuardrailViolationError, match="private, loopback, or reserved"):
        validate_tool_call(tool=tool, request=ToolRequest(target="10.0.0.1", target_type="ip"), scope=ExecutionScope.passive_public())


def test_passive_public_blocks_ssrf_url():
    tool = RegisteredTool(
        name="web_tool",
        description="Web",
        category="web",
        func=_dummy_func,
    )
    # Localhost URL
    with pytest.raises(GuardrailViolationError, match="SSRF"):
        validate_tool_call(tool=tool, request=ToolRequest(target="http://localhost:8080/admin", target_type="url"), scope=ExecutionScope.passive_public())
    # Private IP URL
    with pytest.raises(GuardrailViolationError, match="SSRF"):
        validate_tool_call(tool=tool, request=ToolRequest(target="http://192.168.1.10/status", target_type="url"), scope=ExecutionScope.passive_public())
    # Non-HTTP scheme
    with pytest.raises(GuardrailViolationError, match="disallowed scheme"):
        validate_tool_call(tool=tool, request=ToolRequest(target="ftp://example.com/file", target_type="url"), scope=ExecutionScope.passive_public())


def test_invalid_domain_rejected():
    tool = RegisteredTool(
        name="dns_tool",
        description="DNS",
        category="certificate",
        func=_dummy_func,
    )
    with pytest.raises(GuardrailViolationError, match="not a valid FQDN"):
        validate_tool_call(tool=tool, request=ToolRequest(target="invalid_domain!", target_type="domain"), scope=ExecutionScope.passive_public())


def test_elevated_tool_requires_authorized_mode():
    tool = RegisteredTool(
        name="active_tool",
        description="Active assessment tool",
        category="recon",
        func=_dummy_func,
        required_execution_mode=ExecutionMode.AUTHORIZED_SECURITY_ASSESSMENT,
    )
    # Under passive public
    with pytest.raises(GuardrailViolationError, match="requires AUTHORIZED_SECURITY_ASSESSMENT mode"):
        validate_tool_call(tool=tool, request=ToolRequest(target="example.com", target_type="domain"), scope=ExecutionScope.passive_public())


def test_authorized_mode_without_scope_rejected():
    tool = RegisteredTool(
        name="active_tool",
        description="Active assessment tool",
        category="recon",
        func=_dummy_func,
        required_execution_mode=ExecutionMode.AUTHORIZED_SECURITY_ASSESSMENT,
    )
    # Mode is set to AUTHORIZED_SECURITY_ASSESSMENT, but no authorized targets provided
    bare_scope = ExecutionScope(mode=ExecutionMode.AUTHORIZED_SECURITY_ASSESSMENT)
    with pytest.raises(GuardrailViolationError, match="not self-authorizing"):
        validate_tool_call(tool=tool, request=ToolRequest(target="example.com", target_type="domain"), scope=bare_scope)


def test_authorized_mode_enforces_authorized_domain_membership():
    tool = RegisteredTool(
        name="active_tool",
        description="Active assessment tool",
        category="recon",
        func=_dummy_func,
        required_execution_mode=ExecutionMode.AUTHORIZED_SECURITY_ASSESSMENT,
    )
    elevated_scope = ExecutionScope(
        mode=ExecutionMode.AUTHORIZED_SECURITY_ASSESSMENT,
        authorized_domains=["authorized-target.com"],
        authorized_by="user:analyst",
    )
    # Disallowed target
    with pytest.raises(GuardrailViolationError, match="not in authorized_domains list"):
        validate_tool_call(tool=tool, request=ToolRequest(target="unauthorized.com", target_type="domain"), scope=elevated_scope)

    # Allowed target
    validate_tool_call(tool=tool, request=ToolRequest(target="authorized-target.com", target_type="domain"), scope=elevated_scope)
