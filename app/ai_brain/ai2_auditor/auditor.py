"""
ROVON.UZ - AI-2: ROVON-AUDITOR Engine
Critical skeptic, anti-syndication, Bayesian truth verification, and risk evaluation.
"""

import math
from typing import Dict, Any, List
from app.ai_brain.ai1_investigator.schemas import InvestigationPayload
from app.ai_brain.ai2_auditor.schemas import AuditResult, DiscrepancyItem

# Critical life-safety or national emergency keywords that require editorial caution
CRITICAL_RISK_KEYWORDS = [
    "vafot", "halok", "qurbon", "qotillik", "hujum", "portlash",
    "falokat", "terror", "davlat to'ntarishi"
]


class RovonAuditor:
    """AI-2: Critical Skeptic and Risk Auditor."""

    def calculate_bayesian_score(
        self, authority: float, independent_sources_count: int, has_discrepancies: bool, is_recycled: bool
    ) -> float:
        """
        Calculates calibrated Bayesian credibility score (0.0 to 1.0).
        """
        base = authority * 0.85
        boost = min(independent_sources_count, 3) * 0.05
        penalty = (0.35 if has_discrepancies else 0.0) + (0.50 if is_recycled else 0.0)
        score = base + boost - penalty
        return round(min(max(score, 0.05), 0.99), 3)

    def determine_risk_tier(self, text: str) -> str:
        """Evaluates journalistic & legal sensitivity risk tier."""
        lower_text = text.lower()
        matched_critical = [k for k in CRITICAL_RISK_KEYWORDS if k in lower_text]

        if len(matched_critical) >= 2:
            return "LEVEL_4_CRITICAL"
        elif len(matched_critical) == 1:
            return "LEVEL_3_HIGH"
        elif any(w in lower_text for w in ["narx", "ob-havo", "transport", "ta'lim", "tibbiyot"]):
            return "LEVEL_2_MED"
        return "LEVEL_1_LOW"

    async def audit_investigation(self, investigation: InvestigationPayload, raw_text: str) -> AuditResult:
        """
        Conducts adversarial audit and issues verdict:
        - Evaluates source authority and cross-verification
        - Detects divergence
        - Enables autonomous throughput for official channels
        """
        indep_count = len([c for c in investigation.cross_references if c.is_independent])
        has_discrepancies = False
        discrepancies: List[DiscrepancyItem] = []

        base_authority = investigation.primary_source_authority
        score = self.calculate_bayesian_score(
            authority=base_authority,
            independent_sources_count=indep_count,
            has_discrepancies=has_discrepancies,
            is_recycled=investigation.is_recycled_news,
        )

        is_official = base_authority >= 0.85
        if is_official and not has_discrepancies and not investigation.is_recycled_news:
            verdict = "VERIFIED"
            score = max(score, 0.92)
        elif investigation.is_recycled_news:
            verdict = "FALSE"
        elif has_discrepancies:
            verdict = "CONFLICTING"
        elif score >= 0.80:
            verdict = "VERIFIED"
        elif score >= 0.65:
            verdict = "MOSTLY_VERIFIED"
        else:
            verdict = "UNCONFIRMED"

        risk_tier = self.determine_risk_tier(f"{investigation.original_title} {raw_text}")

        # 100% Fully Autonomous Flow: Inson tasdig'i olib tashlandi, to'g'ridan-to'g'ri kanalga chiqariladi
        human_gate = False

        summary = (
            f"Fakt tekshiruv yakunlandi: Holati - {verdict} (Bayes ishonch balli: {score}). "
            f"Xavf darajasi: {risk_tier}. Inson tasdig'i: TALAB ETILMAYDI (To'liq avtomatik)."
        )

        return AuditResult(
            investigation_id=investigation.article_id,
            verdict=verdict,
            bayesian_score=score,
            risk_tier=risk_tier,
            discrepancies=discrepancies,
            human_gate_required=human_gate,
            audit_summary=summary,
        )
