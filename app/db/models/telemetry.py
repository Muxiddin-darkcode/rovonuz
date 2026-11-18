"""
ROVON.UZ - Database Model: TelemetrySnapshot
Stores real Telegram metrics (views, forwards, reactions) over time for each published post.
"""

import uuid
from datetime import datetime, timezone
from typing import Dict, Any

from sqlalchemy import Integer, DateTime, JSON, Numeric, BigInteger, ForeignKey, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class TelemetrySnapshot(Base):
    __tablename__ = "telemetry_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    time: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True
    )
    queue_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("ai4_publishing_queue.id", ondelete="CASCADE"), nullable=False, index=True
    )
    telegram_message_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    
    views_count: Mapped[int] = mapped_column(Integer, default=0)
    forwards_count: Mapped[int] = mapped_column(Integer, default=0)
    reactions_count: Mapped[int] = mapped_column(Integer, default=0)
    reactions_detail: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict)
    
    virality_velocity: Mapped[float] = mapped_column(Numeric(8, 2), default=0.00)  # dV/dt (views per minute)

    # Relationships
    queue = relationship("AI4PublishingQueue", back_populates="telemetries")

    def __repr__(self) -> str:
        return f"<TelemetrySnapshot(msg_id={self.telegram_message_id}, views={self.views_count}, time={self.time})>"
