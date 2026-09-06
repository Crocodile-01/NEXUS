import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.task import InvestigationTask


class ToolExecution(Base):
    __tablename__ = "tool_executions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    task_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("investigation_tasks.id", ondelete="SET NULL"), nullable=True, index=True
    )
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    execution_mode: Mapped[str] = mapped_column(String(50), default="PASSIVE_PUBLIC")

    input_params: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    status: Mapped[str] = mapped_column(String(50), default="success")
    execution_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    task: Mapped["InvestigationTask | None"] = relationship("InvestigationTask", back_populates="tool_executions")
