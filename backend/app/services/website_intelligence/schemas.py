from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field

from app.agents.schemas import AgentFinding


class TechClassification(str, Enum):
    """Classification of how a technology was identified."""

    EXPLICIT = "EXPLICIT"
    """Explicitly mentioned in visible webpage text or documentation."""

    DETECTED = "DETECTED"
    """Detected directly from HTML metadata, script assets, DOM attributes, or HTTP headers."""

    INFERRED = "INFERRED"
    """Inferred based on detected dependencies or common architectural pairings."""


class DetectedTechnology(BaseModel):
    """Technology detected on the target website."""

    name: str
    category: str = Field(..., description="CMS, Framework, Library, CDN, Web Server, Hosting, Language, Analytics, etc.")
    classification: TechClassification = TechClassification.DETECTED
    evidence_snippet: str = Field(..., description="HTML tag, header value, script src, or text snippet supporting detection")
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)


class OrganizationProfile(BaseModel):
    """Extracted profile of the primary organization operating the website."""

    name: str
    legal_name: str | None = None
    description: str | None = None
    headquarters: str | None = None
    website_url: str
    canonical_domain: str
    domains: list[str] = Field(default_factory=list)
    products_services: list[str] = Field(default_factory=list)
    social_links: list[str] = Field(default_factory=list)


class IdentifiedEntity(BaseModel):
    """Entity identified from website content or enrichment."""

    name: str
    entity_type: str = Field(..., description="COMPANY, PERSON, ORGANIZATION, PRODUCT, PROJECT, TECHNOLOGY, DOMAIN, REPOSITORY, etc.")
    role_or_title: str | None = None
    source_url: str | None = None
    evidence_snippet: str | None = None
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)


class IdentifiedProduct(BaseModel):
    """Product, solution, or project identified on the website."""

    name: str
    description: str | None = None
    product_type: str = "PRODUCT"  # PRODUCT or PROJECT
    source_url: str | None = None
    evidence_snippet: str | None = None
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)


class ReportRelationship(BaseModel):
    """Verified relationship between entities discovered during research."""

    source_entity: str
    source_entity_type: str
    relationship_type: str  # operates, develops, employs, uses, publishes, links_to
    target_entity: str
    target_entity_type: str
    confidence: float = Field(default=0.85, ge=0.0, le=1.0)
    supporting_evidence: str | None = None


class TimelineEvent(BaseModel):
    """Historical or temporal anchor established from public evidence."""

    date_or_year: str
    event_description: str
    source_ref: str | None = None


class WebsiteIntelligenceReport(BaseModel):
    """
    Comprehensive, evidence-backed intelligence report for a website / domain.
    """

    target_url: str
    canonical_domain: str
    investigation_id: str
    generated_at: datetime

    # 1. Executive Summary
    executive_summary: str

    # 2. Organization Profile
    organization_profile: OrganizationProfile

    # 3. People & Organizations
    people_and_organizations: list[IdentifiedEntity] = Field(default_factory=list)

    # 4. Technologies
    technologies: list[DetectedTechnology] = Field(default_factory=list)

    # 5. Projects & Products
    projects_and_products: list[IdentifiedProduct] = Field(default_factory=list)

    # 6. Relationships
    relationships: list[ReportRelationship] = Field(default_factory=list)

    # 7. Evidence & Sources
    sources_consulted: list[str] = Field(default_factory=list)
    evidence_count: int = 0

    # 8. Confidence Assessment & Verified Findings
    findings: list[AgentFinding] = Field(default_factory=list)
    average_confidence: float = 0.0

    # 9. Timeline
    timeline: list[TimelineEvent] = Field(default_factory=list)

    # 10. Research Gaps
    research_gaps: list[str] = Field(default_factory=list)

    model_config = ConfigDict(arbitrary_types_allowed=True)


class InvestigationTimings(BaseModel):
    """Performance timing measurements for investigation lifecycle phases (in milliseconds)."""

    target_validation_ms: float = 0.0
    crawl_ms: float = 0.0
    extraction_ms: float = 0.0
    enrichment_ms: float = 0.0
    total_ms: float = 0.0


class WebsiteInvestigationRequest(BaseModel):
    """Payload for POST /api/v1/investigations/website."""

    target: str = Field(..., description="Target website URL or domain, e.g. https://example.com or example.com")
    objective: str | None = Field(default=None, description="Optional custom research objective")
    max_pages: int = Field(default=3, ge=1, le=10, description="Max internal pages to fetch (bounded crawl)")
    enrich: bool = Field(default=True, description="Enable public OSINT enrichment via Wikidata, crt.sh, etc.")


class WebsiteInvestigationResponse(BaseModel):
    """Response returned by POST /api/v1/investigations/website."""

    investigation_id: str
    status: str
    target: str
    canonical_domain: str
    tasks_count: int
    findings_count: int
    evidence_count: int
    entities_count: int
    relationships_count: int
    timings: InvestigationTimings = Field(default_factory=InvestigationTimings)
    report: WebsiteIntelligenceReport
