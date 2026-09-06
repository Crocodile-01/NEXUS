from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class FindingCreate(BaseModel):
    investigation_id: str
    evidence_id: str | None = None
    claim: str = Field(..., description="Claim or statement extracted from evidence")
    classification: str = Field(default="UNVERIFIED", description="FACT, SUPPORTED_INFERENCE, or UNVERIFIED")
    confidence_score: float = Field(default=0.5, ge=0.0, le=1.0)


class FindingRead(BaseModel):
    id: str
    investigation_id: str
    evidence_id: str | None = None
    claim: str
    classification: str
    confidence_score: float
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
