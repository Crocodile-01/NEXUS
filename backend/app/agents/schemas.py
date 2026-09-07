from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class FindingClassification(str, Enum):
    """
    Strict classification of claims formulated by agents to prevent hallucinations.
    """

    FACT = "FACT"
    """Empirical fact directly backed by verified source evidence."""

    SUPPORTED_INFERENCE = "SUPPORTED_INFERENCE"
    """Logical deduction or correlation derived from one or more verified facts."""

    UNVERIFIED = "UNVERIFIED"
    """Lead, unconfirmed claim, or hypothesis requiring further corroboration."""


class AgentFinding(BaseModel):
    """
    Structured finding output from an agent execution.
    """

    claim: str = Field(..., description="The factual claim or inference statement")
    classification: FindingClassification = Field(
        default=FindingClassification.UNVERIFIED,
        description="FACT, SUPPORTED_INFERENCE, or UNVERIFIED",
    )
    confidence_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Confidence score from 0.0 to 1.0",
    )
    evidence_id: str | None = Field(
        default=None,
        description="UUID of the supporting Evidence record in database",
    )
    source_url: str | None = Field(
        default=None,
        description="URL of source supporting this finding",
    )
    supporting_snippet: str | None = Field(
        default=None,
        description="Exact snippet or excerpt from evidence supporting the finding",
    )

    model_config = ConfigDict(from_attributes=True)


class AgentRunResult(BaseModel):
    """
    Structured outcome of an agent execution cycle.
    """

    investigation_id: str
    agent_role: str = "InvestigationManager"
    model_name: str | None = None
    objective: str
    status: str = "completed"
    findings: list[AgentFinding] = Field(default_factory=list)
    tools_executed: list[str] = Field(default_factory=list)
    summary: str = ""
    execution_time_ms: int = 0

    model_config = ConfigDict(from_attributes=True, arbitrary_types_allowed=True)
