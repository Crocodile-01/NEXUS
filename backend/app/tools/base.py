from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.security.execution_scope import ExecutionMode
from app.sources.base import SourceResult


class ToolRequest(BaseModel):
    """
    Standardized request payload passed to NEXUS registered tools.
    """

    target: str = Field(..., description="Target domain, URL, IP, company name, or research query")
    target_type: str = Field(
        default="general",
        description="Type of target (domain, url, ip, company, person, organization, academic_query, general)",
    )
    limit: int = Field(default=10, ge=1, le=100, description="Max results to fetch")
    params: dict[str, Any] = Field(default_factory=dict, description="Additional tool-specific parameters")

    model_config = ConfigDict(extra="ignore")


class ToolResult(BaseModel):
    """
    Standardized result payload returned from NEXUS tool execution.
    """

    success: bool
    tool_name: str
    target: str
    output_data: dict[str, Any] = Field(default_factory=dict, description="Structured tool outputs")
    source_result: SourceResult | None = Field(
        default=None, description="Normalized SourceResult if the tool wrapped a SourceAdapter"
    )
    error_message: str | None = None
    execution_time_ms: int = 0

    model_config = ConfigDict(arbitrary_types_allowed=True)


class RegisteredTool:
    """
    Metadata and execution callable definition for a tool registered in NEXUS.
    Independent of any specific LLM provider or SDK.
    """

    def __init__(
        self,
        name: str,
        description: str,
        category: str,
        func: Callable[..., Awaitable[ToolResult]],
        input_schema: type[BaseModel] = ToolRequest,
        output_schema: type[BaseModel] = ToolResult,
        required_execution_mode: ExecutionMode = ExecutionMode.PASSIVE_PUBLIC,
        risk_level: str = "LOW",
        timeout: int = 15,
        rate_limit: int = 60,
        enabled: bool = True,
    ) -> None:
        self.name = name
        self.description = description
        self.category = category
        self.func = func
        self.input_schema = input_schema
        self.output_schema = output_schema
        self.required_execution_mode = required_execution_mode
        self.risk_level = risk_level
        self.timeout = timeout
        self.rate_limit = rate_limit
        self.enabled = enabled

    def __repr__(self) -> str:
        return f"<RegisteredTool name='{self.name}' category='{self.category}' enabled={self.enabled}>"
