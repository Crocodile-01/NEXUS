import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:
    from app.models.evidence import Evidence


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False)
    reliability_tier: Mapped[str] = mapped_column(String(50), default="THIRD_PARTY")
    base_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    evidences: Mapped[list["Evidence"]] = relationship("Evidence", back_populates="source")
