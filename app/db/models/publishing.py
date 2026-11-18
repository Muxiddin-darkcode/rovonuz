"""
ROVON.UZ - Database Model: AI4PublishingQueue
Stores the scheduling decisions, priority tiers, and dispatch status.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, Text, DateTime, Numeric, Boolean, BigInteger, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class AI4PublishingQueue(Base):
    __tablename__ = "ai4_publishing_queue"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    editorial_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ai3_editorials.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    hawkes_priority_score: Mapped[float] = mapped_column(Numeric(5, 2), nullable=False)
    # BREAKING, HIGH, NORMAL, LOW
    priority_tier: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    scheduled_slot: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    anti_fatigue_passed: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # WAITING, DISPATCHING, PUBLISHED, FAILED, RETRY_LOCKED
    dispatch_status: Mapped[str] = mapped_column(String(25), default="WAITING", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True, nullable=False, index=True)
    
    telegram_message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)
    dispatched_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    editorial = relationship("AI3Editorial", back_populates="queues")
    telemetries = relationship("TelemetrySnapshot", back_populates="queue", cascade="all, delete-orphan")
    erratas = relationship("EditorialErratum", back_populates="queue", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<AI4PublishingQueue(id={self.id}, tier={self.priority_tier}, slot={self.scheduled_slot}, status={self.dispatch_status})>"
