from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.tools.base import RegisteredTool

logger = logging.getLogger(__name__)


class ToolNotFoundError(Exception):
    """Raised when a requested tool is not found in the registry."""


class ToolDisabledError(Exception):
    """Raised when an operation is attempted on a disabled tool."""


class ToolRegistry:
    """
    Application-level registry managing all available NEXUS tools.
    Independent of LLM and orchestration framework.
    """

    def __init__(self) -> None:
        self._tools: dict[str, RegisteredTool] = {}

    def register(self, tool: RegisteredTool) -> None:
        """
        Register a new tool. Rejects duplicate tool names.
        """
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered in NEXUS ToolRegistry.")
        self._tools[tool.name] = tool
        logger.info("Registered tool: %s (%s)", tool.name, tool.category)

    def get(self, name: str) -> RegisteredTool | None:
        """
        Retrieve a registered tool by name or None if not found.
        """
        return self._tools.get(name)

    def get_or_fail(self, name: str) -> RegisteredTool:
        """
        Retrieve a registered tool by name or raise ToolNotFoundError.
        """
        tool = self.get(name)
        if not tool:
            raise ToolNotFoundError(f"Tool '{name}' is not registered in NEXUS ToolRegistry.")
        return tool

    def list_tools(
        self,
        enabled_only: bool = False,
        category: str | None = None,
    ) -> list[RegisteredTool]:
        """
        List registered tools with optional filtering.
        """
        tools = list(self._tools.values())
        if enabled_only:
            tools = [t for t in tools if t.enabled]
        if category:
            tools = [t for t in tools if t.category == category]
        return tools

    def unregister(self, name: str) -> bool:
        """
        Remove a tool from the registry.
        """
        if name in self._tools:
            del self._tools[name]
            return True
        return False


# Global singleton Tool Registry instance
tool_registry = ToolRegistry()
