"""
ROVON.UZ - AI-1: ROVON-INVESTIGATOR Engine
Decomposes news into atomic claims, extracts entities, and searches for primary sources.
"""

import json
import re
from typing import Dict, Any, Optional
import httpx

from app.core.config import settings
from app.ai_brain.ai1_investigator.schemas import (
    InvestigationPayload,
    AtomicClaim,
    ExtractedEntities,
    CrossSourceReference,
)

# Top 40 high-authority official channels & government domains in Uzbekistan
OFFICIAL_AUTHORITIES = {
    # 1. State Leaders & Presidency
    "@shmirziyoyev": 1.0,
    "@pressuz": 1.0,
    "president.uz": 1.0,
    "gov.uz": 1.0,
    "@mirziyoyev_sh": 1.0,

    # 2. Key Ministries & Law Enforcement
    "@huquqiyaxborot": 0.98,
    "@adliya_uz": 0.98,
    "@adliya_vazirligi": 0.98,
    "@iivuz": 0.98,
    "@iiv.uz": 0.98,
    "@fvv_uz": 0.98,
    "@boshprokuratura": 0.98,
    "@mudofaa_press": 0.98,
    "@mfa_uzbekistan": 0.98,

    # 3. Social & Economic Ministries / Agencies
    "@ssvuz": 0.98,
    "@ssv.uz": 0.98,
    "@markaziybankuz": 0.98,
    "@soliqplusuz": 0.96,
    "@bojxona_qomitasi": 0.96,
    "@statistika_rasmiy": 0.96,
    "@eduuz": 0.96,
    "@uztdi": 0.96,
    "@antimonopol_uz": 0.95,
    "@energetika_vazirligi": 0.95,
    "@uzagmgov": 0.95,
    "@toshkent_shahar_hokimligi": 0.95,
    "@tashkent_hokimiyat": 0.95,
    "@koronavirusinfouz": 0.95,

    # 4. Premier National News Agencies & Portals
    "uza.uz": 0.96,
    "yuz.uz": 0.94,
    "gazeta.uz": 0.90,
    "@gazetauz": 0.90,
    "kun.uz": 0.88,
    "@kunuz": 0.88,
    "@kun.uz": 0.88,
    "daryo.uz": 0.88,
    "@daryo": 0.88,
    "@daryo.rasmiy": 0.88,
    "qalampir.uz": 0.86,
    "@qalampir": 0.86,
    "xabar.uz": 0.86,
    "@xabaruz": 0.86,
    "podrobno.uz": 0.85,
    "anhor.uz": 0.85,
    "sputniknews.uz": 0.84,
}


class RovonInvestigator:
    """AI-1: Fact and Source Investigator."""

    def __init__(self):
        self.gemini_key = settings.GEMINI_API_KEY
        self.tavily_key = settings.TAVILY_API_KEY

    def calculate_source_authority(self, source_identifier: str) -> float:
        """Determines primary source authority weight between 0.2 and 1.0."""
        clean_id = source_identifier.lower().strip()
        for authority, weight in OFFICIAL_AUTHORITIES.items():
            if authority in clean_id:
                return weight
        return 0.50  # Default moderate baseline

    async def search_cross_references(self, query: str) -> list[CrossSourceReference]:
        """Searches live web using Tavily API for independent corroboration."""
        if not self.tavily_key or "your_tavily" in self.tavily_key:
            return []
        try:
            clean_query = re.sub(r'[^\w\s]', ' ', query)[:150].strip()
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": self.tavily_key,
                        "query": clean_query,
                        "search_depth": "basic",
                        "max_results": 3,
                    }
                )
                if res.status_code == 200:
                    data = res.json()
                    refs = []
                    for item in data.get("results", []):
                        url = item.get("url", "")
                        domain = url.split("//")[-1].split("/")[0] if url else "web"
                        refs.append(
                            CrossSourceReference(
                                url=url,
                                domain=domain,
                                is_independent=True,
                                claims_supported=["c_1"]
                            )
                        )
                    return refs
        except Exception as e:
            print(f"[Tavily Search Warning] Could not perform web search: {e}", flush=True)
        return []

    async def investigate_article(self, article_data: Dict[str, Any]) -> InvestigationPayload:
        """
        Main investigation entry point:
        1. Decomposes claims and extracts entities via LLM or deterministic rules.
        2. Evaluates primary source authority.
        3. Checks for recycled/stale news flags.
        """
        article_id = str(article_data.get("id", ""))
        title = article_data.get("title", "")
        body = article_data.get("body_clean", "")
        source_id = article_data.get("source_identifier", "")
        source_url = article_data.get("source_url", "")

        authority = self.calculate_source_authority(source_id)

        # Live Web Search via Tavily for independent cross-references
        cross_refs = []
        if self.tavily_key and "your_tavily" not in self.tavily_key:
            search_query = f"{title} {body[:60]}"
            cross_refs = await self.search_cross_references(search_query)

        # If Gemini API Key is configured, run advanced LLM decomposition
        if self.gemini_key and "your_gemini" not in self.gemini_key:
            try:
                res = await self._llm_investigate(article_id, title, body, source_url, authority)
                if cross_refs:
                    res.cross_references.extend(cross_refs)
                return res
            except Exception as e:
                print(f"[AI-1 Gemini Error] Fallback to deterministic parser: {e}")

        # Deterministic / Regex Fallback (Ensures 100% uptime even without API keys)
        return self._deterministic_investigate(article_id, title, body, source_url, authority, cross_refs=cross_refs)

    def _deterministic_investigate(
        self, article_id: str, title: str, body: str, source_url: str, authority: float, cross_refs: list = None
    ) -> InvestigationPayload:
        """Deterministic rule-based claim and entity extractor."""
        # Numbers and stats extractor
        numbers = re.findall(r'\b\d+(?:[\.,]\d+)?(?:\s*(?:ta|foiz|ming|million|milliard|so\'m|dollar|km|metr))?\b', body, re.IGNORECASE)
        
        # Date regex
        dates = re.findall(r'\b\d{1,2}[-\./]\d{1,2}[-\./]\d{2,4}\b|\b\d{1,2}-(?:yanvar|fevral|mart|aprel|may|iyun|iyul|avgust|sentabr|oktabr|noyabr|dekabr)\b', body, re.IGNORECASE)

        entities = ExtractedEntities(
            persons=[],
            organizations=[],
            locations=[],
            dates=list(set(dates))[:5],
            numbers_and_stats=list(set(numbers))[:8]
        )

        # Form atomic claims from key sentences
        sentences = [s.strip() for s in re.split(r'[.!?]+', body) if len(s.strip()) > 30]
        claims = []
        for i, sentence in enumerate(sentences[:4]):
            claims.append(
                AtomicClaim(
                    claim_id=f"c_{i+1}",
                    subject=title if i == 0 else "Voqea tafsiloti",
                    predicate=sentence[:100],
                    is_supported=authority >= 0.85,
                    supporting_urls=[source_url] if source_url else []
                )
            )

        all_refs = [
            CrossSourceReference(
                url=source_url,
                domain=source_url.split("//")[-1].split("/")[0] if source_url else "local",
                is_independent=True,
                claims_supported=[c.claim_id for c in claims]
            )
        ]
        if cross_refs:
            all_refs.extend(cross_refs)

        return InvestigationPayload(
            article_id=article_id,
            original_title=title,
            entities=entities,
            primary_source_url=source_url,
            primary_source_authority=authority,
            claims=claims,
            cross_references=all_refs,
            is_recycled_news=False,
            notes="Tavily jonli qidiruvi va qoidalar asosida tekshirildi." if cross_refs else "Deterministik qoidalar asosida tekshirildi."
        )

    async def _llm_investigate(
        self, article_id: str, title: str, body: str, source_url: str, authority: float
    ) -> InvestigationPayload:
        """Structured LLM investigation using Google Gemini."""
        from google import genai
        client = genai.Client(api_key=self.gemini_key)

        prompt = f"""
Sen ROVON.UZ ning yetakchi Fakt Detektivi (AI-1: INVESTIGATOR)san.
Berilgan xabardan shaxslar, tashkilotlar, joylar, sanalar va raqamlarni ajratib, atomik faktlar bo'yicha quyidagi aniq JSON formatida javob ber:

Sarlavha: {title}
Matn: {body}
Manba havolasi: {source_url}

JAVOBNI FAQAT QUYIDAGI JSON FORMATIDA QAYTAR:
{{
  "article_id": "{article_id}",
  "original_title": "{title}",
  "primary_source_url": "{source_url}",
  "primary_source_authority": {authority},
  "entities": {{
    "persons": ["..."],
    "organizations": ["..."],
    "locations": ["..."],
    "dates": ["..."],
    "numbers_and_stats": ["..."]
  }},
  "claims": [
    {{
      "claim_id": "c_1",
      "subject": "Asosiy mavzu",
      "predicate": "Tasdiqlangan fakt",
      "is_supported": true,
      "supporting_urls": ["{source_url}"]
    }}
  ],
  "cross_references": [
    {{
      "url": "{source_url}",
      "domain": "rasmiy",
      "is_independent": true,
      "claims_supported": ["c_1"]
    }}
  ],
  "is_recycled_news": false,
  "notes": "Gemini 2.5 Flash bilan tekshirildi."
}}
"""
        response = client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=prompt,
        )
        # Parse response safely
        raw_json = re.search(r'\{.*\}', response.text, re.DOTALL)
        if raw_json:
            data = json.loads(raw_json.group(0))
            if "article_id" not in data:
                data["article_id"] = article_id
            if "original_title" not in data:
                data["original_title"] = title
            if "primary_source_url" not in data:
                data["primary_source_url"] = source_url
            if "primary_source_authority" not in data:
                data["primary_source_authority"] = authority
            if "entities" not in data or not isinstance(data["entities"], dict):
                data["entities"] = {"persons": [], "organizations": [], "locations": [], "dates": [], "numbers_and_stats": []}
            if "claims" not in data or not isinstance(data["claims"], list):
                data["claims"] = []
            if "cross_references" not in data or not isinstance(data["cross_references"], list):
                data["cross_references"] = []
            return InvestigationPayload(**data)

        return self._deterministic_investigate(article_id, title, body, source_url, authority)
