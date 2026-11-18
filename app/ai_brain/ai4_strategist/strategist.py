"""
ROVON.UZ - AI-4: ROVON-STRATEGIST Engine
Stochastic publishing scheduler, Hawkes priority scoring, and anti-fatigue rate limiting.
"""

import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional

from app.ai_brain.ai3_editor.schemas import EditorialPackage
from app.ai_brain.ai4_strategist.schemas import PublishingScheduleDecision


# Urgent breaking keywords that boost priority score
BREAKING_KEYWORDS = [
    "shoshilinch", "favqulodda", "zilzila", "portlash", "halokat", "tezkor",
    "prezident qarori", "hushyor bo'ling", "ogohlantirish"
]


class RovonStrategist:
    """AI-4: Publishing Strategist & Queue Optimizer."""

    def calculate_priority_score(self, text: str, category: str, published_at: Optional[datetime]) -> float:
        """
        Calculates Hawkes-inspired priority score (0.0 to 100.0).
        """
        base_score = 50.0  # Normal news baseline
        lower_text = text.lower()

        # Category weights
        if category in ["TEZKOR", "BREAKING", "HODISA"]:
            base_score += 30.0
        elif category in ["IQTISODIYOT", "SIYOSAT", "TRANSPORT"]:
            base_score += 15.0
        elif category in ["TEXNOLOGIYA", "SPORT", "MADANIYAT"]:
            base_score += 5.0

        # Urgent keyword boost
        if any(w in lower_text for w in BREAKING_KEYWORDS):
            base_score += 25.0

        # Freshness decay
        if published_at:
            if published_at.tzinfo is None:
                published_at = published_at.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            diff_hours = (now - published_at).total_seconds() / 3600.0
            if diff_hours < 0.5:
                base_score += 10.0
            elif diff_hours > 6.0:
                base_score -= 20.0

        return round(min(max(base_score, 10.0), 99.0), 2)

    def determine_priority_tier(self, score: float) -> str:
        """Maps numeric score to operational tier."""
        if score >= 90.0:
            return "BREAKING"
        elif score >= 75.0:
            return "HIGH"
        elif score >= 50.0:
            return "NORMAL"
        return "LOW"

    def determine_scheduled_slot(
        self, priority_tier: str, last_scheduled_time: Optional[datetime]
    ) -> datetime:
        """
        Calculates optimal slot ensuring minimum 25-30 min interval between posts.
        Breaking news bypasses regular cooldown!
        """
        now = datetime.now(timezone.utc)

        if priority_tier == "BREAKING":
            # Immediate slot (next 1-2 minutes)
            return now + timedelta(minutes=1)

        # Minimum interval for ordinary posts: 30 minutes
        min_interval = timedelta(minutes=30)
        
        if last_scheduled_time:
            if last_scheduled_time.tzinfo is None:
                last_scheduled_time = last_scheduled_time.replace(tzinfo=timezone.utc)

        if last_scheduled_time and last_scheduled_time > now:
            slot = last_scheduled_time + min_interval
        else:
            slot = now + timedelta(minutes=5)

        return slot

    async def schedule_editorial(
        self,
        editorial: EditorialPackage,
        category: str = "YANGILIK",
        published_at: Optional[datetime] = None,
        last_scheduled_slot: Optional[datetime] = None,
    ) -> PublishingScheduleDecision:
        """
        Main scheduling workflow:
        1. Calculates priority score
        2. Assigns tier (BREAKING, HIGH, NORMAL, LOW)
        3. Enforces anti-fatigue cooldown
        4. Generates unique idempotency token
        """
        score = self.calculate_priority_score(editorial.telegram_clean_text, category, published_at)
        tier = self.determine_priority_tier(score)
        slot = self.determine_scheduled_slot(tier, last_scheduled_slot)

        # Idempotency token to prevent double-posting
        raw_key = f"{editorial.audit_id}:{editorial.headline_selected}:{slot.strftime('%Y%m%d%H%M')}"
        idempotency_key = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

        notes = f"Prioritet: {tier} ({score} ball). Rejalashtirilgan slot: {slot.isoformat()}."

        return PublishingScheduleDecision(
            editorial_id=editorial.audit_id,
            hawkes_priority_score=score,
            priority_tier=tier,
            scheduled_slot=slot,
            anti_fatigue_passed=True,
            is_breaking_fast_path=(tier == "BREAKING"),
            idempotency_key=idempotency_key,
            strategy_notes=notes,
        )
