"""
ROVON.UZ - Database Models: AI1Investigation & AI2Audit
Stores decomposed claims, cross-references, and Bayesian audit verdicts.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

from sqlalchemy import String, Text, DateTime, JSON, Numeric, Boolean, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class AI1Investigation(Base):
    __tablename__ = "ai1_investigations"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    article_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("raw_articles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    extracted_entities: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    claims_decomposed: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)
    primary_source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    primary_source_authority: Mapped[Optional[float]] = mapped_column(Numeric(3, 2), default=0.50)
    cross_sources: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)
    is_recycled: Mapped[bool] = mapped_column(Boolean, default=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    article = relationship("RawArticle", back_populates="investigations")
    audits = relationship("AI2Audit", back_populates="investigation", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<AI1Investigation(id={self.id}, article_id={self.article_id}, claims_count={len(self.claims_decomposed)})>"


class AI2Audit(Base):
    __tablename__ = "ai2_audits"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    investigation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ai1_investigations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    # VERIFIED, MOSTLY_VERIFIED, PARTIALLY_VERIFIED, UNCONFIRMED, CONFLICTING, FALSE
    verdict: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    bayesian_score: Mapped[float] = mapped_column(Numeric(4, 3), nullable=False)  # 0.000 to 1.000
    
    # LEVEL_1_LOW, LEVEL_2_MED, LEVEL_3_HIGH, LEVEL_4_CRITICAL
    risk_tier: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    discrepancies: Mapped[List[Dict[str, Any]]] = mapped_column(JSON, default=list)
    
    human_gate_required: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    human_approved_by: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    human_approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    
    audited_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )

    # Relationships
    investigation = relationship("AI1Investigation", back_populates="audits")
    editorials = relationship("AI3Editorial", back_populates="audit", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<AI2Audit(id={self.id}, verdict={self.verdict}, score={self.bayesian_score}, risk={self.risk_tier})>"
