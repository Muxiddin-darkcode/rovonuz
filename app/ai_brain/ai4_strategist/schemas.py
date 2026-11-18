"""
ROVON.UZ - AI-4 (Strategist) Pydantic Schemas
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class PublishingScheduleDecision(BaseModel):
    editorial_id: str
    hawkes_priority_score: float = Field(ge=0.0, le=100.0)
    priority_tier: str = Field(description="BREAKING, HIGH, NORMAL, LOW")
    scheduled_slot: datetime
    anti_fatigue_passed: bool = True
    is_breaking_fast_path: bool = False
    idempotency_key: str
    strategy_notes: str
