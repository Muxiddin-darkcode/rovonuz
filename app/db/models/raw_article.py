"""
ROVON.UZ - Database Model: RawArticle
Represents raw scraped information from Telegram, Web, or Instagram.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import String, Text, DateTime, JSON, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.config import settings
from app.db.session import Base

try:
    from pgvector.sqlalchemy import Vector
    HAS_PGVECTOR = True and ("sqlite" not in settings.DATABASE_URL)
except ImportError:
    HAS_PGVECTOR = False


class RawArticle(Base):
    __tablename__ = "raw_articles"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    source_url: Mapped[str] = mapped_column(Text, unique=True, nullable=False, index=True)
    source_identifier: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(
        String(30), nullable=False, index=True
    )  # TELEGRAM_CHANNEL, WEB_SCRAPER, WEB_RSS, INSTAGRAM_PUBLIC
    
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    body_raw: Mapped[str] = mapped_column(Text, nullable=False)
    body_clean: Mapped[str] = mapped_column(Text, nullable=False)
    category_predicted: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
    
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    media_urls: Mapped[list] = mapped_column(JSON, default=list)
    
    # 1536-dimensional embedding vector for semantic deduplication
    if HAS_PGVECTOR:
        embedding = mapped_column(Vector(1536), nullable=True)
    else:
        embedding = mapped_column(JSON, nullable=True)
        
    cluster_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("raw_articles.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    investigations = relationship("AI1Investigation", back_populates="article", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<RawArticle(id={self.id}, source={self.source_identifier}, type={self.source_type})>"
