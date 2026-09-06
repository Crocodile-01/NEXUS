from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EvidenceCreate(BaseModel):
    source_id: str | None = None
    url: str | None = None
    raw_content_ref: str | None = None
    extracted_snippet: str = Field(..., description="Key extracted evidence snippet")
    publication_date: datetime | None = None
    content_hash: str | None = None


class EvidenceRead(BaseModel):
    id: str
    source_id: str | None = None
    url: str | None = None
    raw_content_ref: str | None = None
    extracted_snippet: str
    retrieved_at: datetime
    publication_date: datetime | None = None
    content_hash: str | None = None

    model_config = ConfigDict(from_attributes=True)
