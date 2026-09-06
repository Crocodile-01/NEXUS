from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class EntityAliasRead(BaseModel):
    id: str
    entity_id: str
    alias_name: str
    source_provenance: str | None = None

    model_config = ConfigDict(from_attributes=True)


class EntityCreate(BaseModel):
    canonical_name: str
    entity_type: str
    confidence_score: float = Field(default=1.0, ge=0.0, le=1.0)
    metadata_json: dict | None = None
    aliases: list[str] = []


class EntityRead(BaseModel):
    id: str
    canonical_name: str
    entity_type: str
    confidence_score: float
    metadata_json: dict | None = None
    created_at: datetime
    updated_at: datetime
    aliases: list[EntityAliasRead] = []

    model_config = ConfigDict(from_attributes=True)
