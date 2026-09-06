import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.finding import Finding
    from app.models.source import Source


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    source_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("sources.id", ondelete="SET NULL"), nullable=True, index=True
    )
    url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    raw_content_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_snippet: Mapped[str] = mapped_column(Text, nullable=False)

    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    publication_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, unique=True, index=True)

    source: Mapped["Source | None"] = relationship("Source", back_populates="evidences")
    findings: Mapped[list["Finding"]] = relationship("Finding", back_populates="evidence")
