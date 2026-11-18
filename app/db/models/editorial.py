"""
ROVON.UZ - Database Model: AI3Editorial
Stores styled, formatted Telegram posts, headline variants, and visual card configuration.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from sqlalchemy import String, Text, DateTime, JSON, Integer, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class AI3Editorial(Base):
    __tablename__ = "ai3_editorials"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    audit_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ai2_audits.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    headline_selected: Mapped[str] = mapped_column(Text, nullable=False)
    headline_alternatives: Mapped[List[str]] = mapped_column(JSON, default=list)
    telegram_clean_text: Mapped[str] = mapped_column(Text, nullable=False)
    character_count: Mapped[int] = mapped_column(Integer, nullable=False)
    
    visual_card_config: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    generated_card_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    diff_from_raw: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    authored_by: Mapped[str] = mapped_column(String(50), default="AI3_ROVON_EDITOR")
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    audit = relationship("AI2Audit", back_populates="editorials")
    queues = relationship("AI4PublishingQueue", back_populates="editorial", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<AI3Editorial(id={self.id}, headline='{self.headline_selected[:30]}...', chars={self.character_count})>"
