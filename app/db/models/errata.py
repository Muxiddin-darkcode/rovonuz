"""
ROVON.UZ - Database Model: EditorialErratum
Tracks retractions, amendments, and corrections issued according to journalistic integrity standards.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import String, Text, DateTime, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class EditorialErratum(Base):
    __tablename__ = "editorial_errata"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    queue_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ai4_publishing_queue.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    # INLINE_EDIT, FORMAL_RETRACTION
    erratum_type: Mapped[str] = mapped_column(String(30), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    corrected_text: Mapped[str] = mapped_column(Text, nullable=False)
    authorized_by: Mapped[str] = mapped_column(String(50), nullable=False)
    
    applied_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )

    # Relationships
    queue = relationship("AI4PublishingQueue", back_populates="erratas")

    def __repr__(self) -> str:
        return f"<EditorialErratum(id={self.id}, type={self.erratum_type}, by={self.authorized_by})>"
