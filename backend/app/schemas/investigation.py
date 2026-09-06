from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class InvestigationTaskRead(BaseModel):
    id: str
    investigation_id: str
    name: str
    task_type: str
    depth_level: int
    status: str
    input_data: dict | None = None
    output_data: dict | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class InvestigationCreate(BaseModel):
    target: str = Field(..., description="Target name, domain, company, person, IP, or research topic")
    target_type: str = Field(default="company", description="company, person, domain, ip, url, technology, project")
    objective: str | None = Field(default=None, description="Optional detailed research goal or prompt")
    max_depth: int = Field(default=3, ge=0, le=5)
    max_tasks: int = Field(default=50, ge=1, le=200)
    mode: str = Field(default="PASSIVE_PUBLIC", description="PASSIVE_PUBLIC or AUTHORIZED_SECURITY_ASSESSMENT")


class InvestigationUpdate(BaseModel):
    status: str | None = None
    objective: str | None = None
    max_depth: int | None = None
    max_tasks: int | None = None


class InvestigationRead(BaseModel):
    id: str
    target: str
    target_type: str
    objective: str | None = None
    max_depth: int
    max_tasks: int
    status: str
    mode: str
    created_at: datetime
    updated_at: datetime
    tasks: list[InvestigationTaskRead] = []

    model_config = ConfigDict(from_attributes=True)
