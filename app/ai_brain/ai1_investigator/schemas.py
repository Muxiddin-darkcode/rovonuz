"""
ROVON.UZ - AI-1 (Investigator) Pydantic Schemas
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class AtomicClaim(BaseModel):
    claim_id: str
    subject: str = Field(description="Who or what the claim is about")
    predicate: str = Field(description="Action, event, or state")
    object: Optional[str] = Field(None, description="Target or result")
    timestamp_claimed: Optional[str] = Field(None, description="Date or time mentioned")
    geo_location: Optional[str] = Field(None, description="City, region, or address")
    magnitude: Optional[str] = Field(None, description="Numbers, statistics, percentages, casualties")
    is_supported: bool = Field(False, description="Whether cross-source evidence was found")
    supporting_urls: List[str] = Field(default_factory=list)


class ExtractedEntities(BaseModel):
    persons: List[str] = Field(default_factory=list)
    organizations: List[str] = Field(default_factory=list)
    locations: List[str] = Field(default_factory=list)
    dates: List[str] = Field(default_factory=list)
    numbers_and_stats: List[str] = Field(default_factory=list)


class CrossSourceReference(BaseModel):
    url: str
    domain: str
    is_independent: bool = True
    claims_supported: List[str] = Field(default_factory=list)
    claims_disputed: List[str] = Field(default_factory=list)


class InvestigationPayload(BaseModel):
    article_id: str
    original_title: str
    entities: ExtractedEntities
    primary_source_url: Optional[str] = None
    primary_source_authority: float = Field(0.5, ge=0.0, le=1.0)
    claims: List[AtomicClaim] = Field(default_factory=list)
    cross_references: List[CrossSourceReference] = Field(default_factory=list)
    is_recycled_news: bool = False
    notes: Optional[str] = None
