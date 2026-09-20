from __future__ import annotations

from datetime import UTC, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.agents.schemas import FindingClassification
from app.services.website_intelligence.schemas import TimelineEvent


class ResearchCategory(str, Enum):
    """Core intelligence investigation categories."""
    IDENTITY = "identity"
    ORGANIZATION = "organization"
    PEOPLE = "people"
    TECHNOLOGY = "technology"
    INFRASTRUCTURE = "infrastructure"
    RESEARCH = "research"
    EXTERNAL_INTELLIGENCE = "external_intelligence"
    TEMPORAL = "temporal"
    GAPS = "gaps"


class PlannerLimits(BaseModel):
    """Bounded investigation execution limits."""
    max_depth: int = Field(default=2, ge=1, le=5, description="Maximum recursion/expansion depth")
    max_total_entities: int = Field(default=50, ge=5, le=200, description="Upper bound on tracked entities")
    max_new_entities_per_task: int = Field(default=5, ge=1, le=20, description="Limit on new entities per research task")
    max_source_queries: int = Field(default=15, ge=1, le=50, description="Total budget of external source adapter queries")
    max_execution_time_seconds: float = Field(default=60.0, ge=5.0, le=300.0, description="Investigation timeout ceiling")
    max_expansions_per_entity: int = Field(default=2, ge=1, le=5, description="Maximum secondary queries spawned per entity")
    min_relevance_score: float = Field(default=0.6, ge=0.0, le=1.0, description="Relevance score threshold for entity expansion")


class ResearchQuestion(BaseModel):
    """Structured, bounded research question addressing an intelligence dimension."""
    id: str
    question: str
    category: ResearchCategory
    priority: float = Field(default=0.5, ge=0.0, le=1.0)
    target_entity: str
    target_entity_type: str = "general"
    suggested_sources: list[str] = Field(default_factory=list)
    depth: int = Field(default=0, ge=0)
    status: str = Field(default="pending")  # pending, in_progress, answered, unanswerable
    rationale: str = ""
    findings_count: int = 0
    sources_queried: list[str] = Field(default_factory=list)


class ResearchPlan(BaseModel):
    """Collection of prioritized research questions with execution tracking."""
    investigation_id: str
    target: str
    target_type: str
    limits: PlannerLimits = Field(default_factory=PlannerLimits)
    questions: list[ResearchQuestion] = Field(default_factory=list)
    total_queries_executed: int = 0
    entities_discovered: int = 0


class EntityExpansionLead(BaseModel):
    """An entity identified as a candidate for secondary investigation."""
    entity_name: str
    entity_type: str
    discovered_via: str
    depth: int
    relevance_score: float = Field(default=0.8, ge=0.0, le=1.0)
    relationship_chain: list[tuple[str, str, str]] = Field(default_factory=list)
    expanded: bool = False


class CorroboratedFinding(BaseModel):
    """
    Evidence-backed intelligence finding with corroboration status,
    confidence rating, and clear 'Why' rationale.
    """
    id: str = ""
    claim: str
    classification: FindingClassification  # FACT, SUPPORTED_INFERENCE, UNVERIFIED
    confidence_score: float = Field(ge=0.0, le=1.0)
    why: str = Field(description="Explanation of why this claim holds this classification and confidence")
    sources: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    related_entities: list[str] = Field(default_factory=list)
    temporal_anchor: str | None = None
    is_corroborated: bool = False
    conflicting_signals: list[str] = Field(default_factory=list)


class TypedRelationship(BaseModel):
    """Typed relationship edge with evidence provenance and confidence."""
    subject: str
    subject_type: str
    predicate: str
    object: str
    object_type: str
    confidence: float = Field(ge=0.0, le=1.0)
    classification: str = "FACT"
    evidence_id: str | None = None
    source_name: str = ""
    supporting_text: str = ""


class IntelligenceReport(BaseModel):
    """Executive-grade, high-signal intelligence report."""
    target: str
    target_type: str
    canonical_domain: str | None = None
    investigation_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # 1. Executive Summary & Profile
    executive_intelligence: str
    target_profile: dict[str, Any] = Field(default_factory=dict)
    organization: dict[str, Any] = Field(default_factory=dict)

    # 2. Key Dimensions
    products_and_projects: list[dict[str, Any]] = Field(default_factory=list)
    people_and_leadership: list[dict[str, Any]] = Field(default_factory=list)
    technology_intelligence: list[dict[str, Any]] = Field(default_factory=list)
    digital_infrastructure: dict[str, Any] = Field(default_factory=dict)
    research_and_publications: list[dict[str, Any]] = Field(default_factory=list)

    # 3. Graph & Corroborated Findings
    relationship_intelligence: list[TypedRelationship] = Field(default_factory=list)
    key_findings: list[CorroboratedFinding] = Field(default_factory=list)
    timeline: list[TimelineEvent] = Field(default_factory=list)

    # 4. Rigor & Integrity
    research_gaps: list[str] = Field(default_factory=list)
    evidence_catalog: list[dict[str, Any]] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)


class IntelligenceInvestigationRequest(BaseModel):
    """Request payload for multi-source intelligence investigation."""
    target: str = Field(..., description="Target URL, domain, company name, or project", min_length=2)
    target_type: str = Field(default="domain", description="Target type: domain, company, organization, project, url")
    objective: str | None = Field(default=None, description="Investigation objective or specific intelligence query")
    max_depth: int = Field(default=2, ge=1, le=4, description="Maximum research expansion depth")
    max_source_queries: int = Field(default=15, ge=3, le=40, description="Max external source queries")
    allow_expansion: bool = Field(default=True, description="Allow bounded secondary entity expansion")


class IntelligenceInvestigationResponse(BaseModel):
    """Response payload for multi-source intelligence investigation."""
    investigation_id: str
    status: str  # completed, failed, partial
    target: str
    target_type: str
    canonical_domain: str | None = None
    tasks_count: int
    findings_count: int
    corroborated_findings_count: int
    entities_count: int
    relationships_count: int
    evidence_count: int
    sources_consulted: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    report: IntelligenceReport
