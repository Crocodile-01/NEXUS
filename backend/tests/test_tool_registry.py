from __future__ import annotations

import pytest

from app.security.execution_scope import ExecutionMode
from app.tools.base import RegisteredTool, ToolRequest, ToolResult
from app.tools.registry import ToolRegistry, tool_registry


async def _dummy_func(request: ToolRequest) -> ToolResult:
    return ToolResult(
        success=True,
        tool_name="dummy_tool",
        target=request.target,
        output_data={"echo": request.target},
    )


def test_tool_registration():
    reg = ToolRegistry()
    tool = RegisteredTool(
        name="custom_tool",
        description="A test tool",
        category="test",
        func=_dummy_func,
    )
    reg.register(tool)
    assert reg.get("custom_tool") is tool
    assert tool in reg.list_tools()


def test_duplicate_tool_rejection():
    reg = ToolRegistry()
    tool1 = RegisteredTool(
        name="duplicate_tool",
        description="First instance",
        category="test",
        func=_dummy_func,
    )
    tool2 = RegisteredTool(
        name="duplicate_tool",
        description="Second instance",
        category="test",
        func=_dummy_func,
    )
    reg.register(tool1)
    with pytest.raises(ValueError, match="already registered"):
        reg.register(tool2)


def test_tool_lookup_and_filtering():
    reg = ToolRegistry()
    t1 = RegisteredTool(
        name="active_tool",
        description="Active",
        category="company",
        func=_dummy_func,
        enabled=True,
    )
    t2 = RegisteredTool(
        name="disabled_tool",
        description="Disabled",
        category="academic",
        func=_dummy_func,
        enabled=False,
    )
    reg.register(t1)
    reg.register(t2)

    assert len(reg.list_tools()) == 2
    assert len(reg.list_tools(enabled_only=True)) == 1
    assert reg.list_tools(enabled_only=True)[0].name == "active_tool"
    assert len(reg.list_tools(category="academic")) == 1
    assert reg.get("nonexistent") is None


def test_global_registry_native_tools():
    """Verify that all standard native tools are registered globally on import."""
    expected_tools = [
        "lookup_certificate_transparency",
        "search_wikidata",
        "lookup_sec_company",
        "search_arxiv",
        "search_semantic_scholar",
        "fetch_webpage",
        "extract_web_content",
        "resolve_entity",
    ]
    for name in expected_tools:
        tool = tool_registry.get(name)
        assert tool is not None, f"Expected tool '{name}' in global registry"
        assert tool.enabled is True
        assert tool.required_execution_mode == ExecutionMode.PASSIVE_PUBLIC
