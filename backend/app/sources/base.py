import hashlib
from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field


class RawEvidence(BaseModel):
    source_name: str
    url: str | None = None
    extracted_snippet: str = Field(..., description="Normalized text snippet or claim extracted from source")
    raw_content: str | None = None
    publication_date: str | None = None
    content_hash: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, context: Any) -> None:
        if not self.content_hash and self.extracted_snippet:
            hash_input = f"{self.source_name}:{self.url or ''}:{self.extracted_snippet}".encode()
            self.content_hash = hashlib.sha256(hash_input).hexdigest()


class ExtractedEntity(BaseModel):
    name: str = Field(..., description="Canonical or extracted entity name")
    entity_type: str = Field(..., description="COMPANY, PERSON, DOMAIN, IP, TECHNOLOGY, PROJECT, RESEARCH_PAPER, etc.")
    aliases: list[str] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExtractedRelationship(BaseModel):
    source_entity: str
    source_entity_type: str
    target_entity: str
    target_entity_type: str
    relationship_type: str  # develops, uses, owns_domain, authored, resolves_to, associated_with
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)


class SourceResult(BaseModel):
    success: bool
    source_name: str
    query: str
    evidence: list[RawEvidence] = Field(default_factory=list)
    entities: list[ExtractedEntity] = Field(default_factory=list)
    relationships: list[ExtractedRelationship] = Field(default_factory=list)
    error_message: str | None = None


class SourceMetadata(BaseModel):
    name: str
    category: str  # certificate, company, academic, web, dns, username, tech
    reliability_tier: str  # OFFICIAL, REPUTABLE, THIRD_PARTY, UNVERIFIED
    is_passive: bool = True
    rate_limit_per_minute: int = 60
    timeout_seconds: int = 15


class SourceAdapter(ABC):
    @property
    @abstractmethod
    def metadata(self) -> SourceMetadata:
        """Return adapter metadata including name, reliability, rate limits."""

    async def search(self, query: str, limit: int = 10) -> SourceResult:
        """Execute a search query against the source."""
        return SourceResult(
            success=False,
            source_name=self.metadata.name,
            query=query,
            error_message="Search method not implemented for this adapter",
        )

    async def fetch(self, target: str) -> SourceResult:
        """Fetch details for a specific target identifier or URL."""
        return SourceResult(
            success=False,
            source_name=self.metadata.name,
            query=target,
            error_message="Fetch method not implemented for this adapter",
        )

    def normalize(self, raw_data: str) -> str:
        """Normalize raw text content."""
        return raw_data.strip()

    def extract_entities(self, content: str) -> list[ExtractedEntity]:
        """Extract entity mentions from text content."""
        return []

    def extract_relationships(self, content: str) -> list[ExtractedRelationship]:
        """Extract relationship edges from content."""
        return []
