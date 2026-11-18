"""
ROVON.UZ - AI-2 (Auditor) Pydantic Schemas
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class DiscrepancyItem(BaseModel):
    field: str
    claim_a: str
    claim_b: str
    resolution_recommendation: str


class AuditResult(BaseModel):
    investigation_id: str
    verdict: str = Field(description="VERIFIED, MOSTLY_VERIFIED, UNCONFIRMED, CONFLICTING, FALSE")
    bayesian_score: float = Field(ge=0.0, le=1.0)
    risk_tier: str = Field(description="LEVEL_1_LOW, LEVEL_2_MED, LEVEL_3_HIGH, LEVEL_4_CRITICAL")
    discrepancies: List[DiscrepancyItem] = Field(default_factory=list)
    human_gate_required: bool = False
    audit_summary: str
