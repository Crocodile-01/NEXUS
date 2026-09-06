import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.entity import Entity
    from app.models.evidence import Evidence


class Relationship(Base):
    __tablename__ = "relationships"
    __table_args__ = (
        Index("idx_rel_src_tgt_type", "source_entity_id", "target_entity_id", "relationship_type"),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    source_entity_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    target_entity_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("entities.id", ondelete="CASCADE"), nullable=False, index=True
    )
    relationship_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=1.0)

    evidence_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("evidence.id", ondelete="SET NULL"), nullable=True, index=True
    )

    first_observed: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    last_observed: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships ORM
    source_entity: Mapped["Entity"] = relationship("Entity", foreign_keys=[source_entity_id])
    target_entity: Mapped["Entity"] = relationship("Entity", foreign_keys=[target_entity_id])
    evidence: Mapped["Evidence | None"] = relationship("Evidence")
