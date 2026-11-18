"""
ROVON.UZ - AI-3 (Editor) Pydantic Schemas
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class VisualCardDirective(BaseModel):
    template: str = Field("STANDARD_NEWS_16_9", description="BREAKING, QUOTE, STATS, STANDARD_NEWS_16_9")
    badge_text: str = Field("YANGILIK", description="Category or priority badge")
    badge_color: str = Field("#0055FF", description="Hex color")
    headline_for_card: str
    image_source_url: Optional[str] = None


class EditorialPackage(BaseModel):
    audit_id: str
    headline_selected: str
    headline_alternatives: List[str] = Field(default_factory=list)
    telegram_clean_text: str
    character_count: int
    visual_card_directive: VisualCardDirective
    diff_from_raw: Optional[str] = None
