import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.evidence import Evidence
    from app.models.investigation import Investigation


class Finding(Base):
    __tablename__ = "findings"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    investigation_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("investigations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    evidence_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("evidence.id", ondelete="SET NULL"), nullable=True, index=True
    )
    claim: Mapped[str] = mapped_column(Text, nullable=False)

    # FACT | SUPPORTED_INFERENCE | UNVERIFIED
    classification: Mapped[str] = mapped_column(String(50), default="UNVERIFIED", index=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.5)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    investigation: Mapped["Investigation"] = relationship("Investigation", back_populates="findings")
    evidence: Mapped["Evidence | None"] = relationship("Evidence", back_populates="findings")
