"""
ROVON.UZ - AI-3: ROVON-EDITOR Engine
Transforms verified facts into elegant, professional Telegram news posts and visual card directives.
Strictly adheres to the Zero-Distortion Rule (never alters facts, figures, or names).
"""

import json
import re
from typing import Dict, Any, List, Optional

from app.core.config import settings
from app.ingestion.sanitizer import convert_to_new_uzbek_alphabet, is_russian_text, translate_to_uzbek
from app.ai_brain.ai2_auditor.schemas import AuditResult
from app.ai_brain.ai3_editor.schemas import EditorialPackage, VisualCardDirective


class RovonEditor:
    """AI-3: Chief Copywriter & Style Transformer."""

    def __init__(self):
        self.gemini_key = settings.GEMINI_API_KEY

    async def craft_editorial_package(
        self,
        audit: AuditResult,
        title: str,
        clean_body: str,
        category: str = "YANGILIK",
        media_urls: Optional[List[str]] = None,
    ) -> EditorialPackage:
        """
        Creates professional Telegram post and visual card directives.
        """
        media_img = media_urls[0] if media_urls else None

        # Ensure all incoming texts are in natural Uzbek
        if is_russian_text(title):
            title = translate_to_uzbek(title)
        if is_russian_text(clean_body):
            clean_body = translate_to_uzbek(clean_body)

        if self.gemini_key:
            try:
                return await self._llm_craft(audit.investigation_id, title, clean_body, category, media_img)
            except Exception as e:
                print(f"[AI-3 Gemini Error] Fallback to deterministic styler: {e}")

        return self._deterministic_craft(audit.investigation_id, title, clean_body, category, media_img)

    def _deterministic_craft(
        self, audit_id: str, title: str, clean_body: str, category: str, media_img: Optional[str]
    ) -> EditorialPackage:
        """Deterministic formatter conforming to Telegram UX standards."""
        # Split body into coherent sentences
        sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', clean_body) if len(s.strip()) > 15]

        # Clean and validate headline
        clean_title = re.sub(r'^[#@\w\s_]*[❗️⚡️🔴⚖️🔰📢📌🔹🔸🔺🔷🔶👉✅❌❓👇]+\s*', '', title or '').strip()
        clean_title = re.sub(r'[\U0001f600-\U0001f64f\U0001f300-\U0001f5ff\U0001f680-\U0001f6ff\U0001f900-\U0001f9ff]+', '', clean_title).strip()

        if len(clean_title) >= 15:
            headline = clean_title
        elif sentences:
            headline = sentences[0][:80]
        else:
            headline = "Muhim rasmiy axborot"

        # Determine lead without duplicating headline
        lead = sentences[0] if sentences else headline
        if sentences and (headline.lower() in lead.lower() or lead.lower() in headline.lower()):
            if len(sentences) > 1:
                body_middle = " ".join(sentences[1:3])
                conclusion = sentences[3] if len(sentences) > 3 else ""
            else:
                body_middle = ""
                conclusion = ""
        else:
            body_middle = " ".join(sentences[1:3]) if len(sentences) > 1 else ""
            conclusion = sentences[3] if len(sentences) > 3 else ""

        # Construct clean journalistic post (ONE headline at the top, clean body paragraphs)
        post_lines = [
            f"{lead}",
        ]
        if body_middle:
            post_lines.extend(["", f"{body_middle}"])
        if conclusion:
            post_lines.extend(["", f"ℹ️ _{conclusion}_"])

        post_lines.extend(["", "🔗 @rovonuz — Tezkor va ishonchli axborot"])

        telegram_text = "\n".join(post_lines)

        # Convert all texts to the NEW Uzbek Latin Alphabet (Ö, Ğ, Ş, Ç)
        headline = convert_to_new_uzbek_alphabet(headline)
        telegram_text = convert_to_new_uzbek_alphabet(telegram_text)
        category_clean = convert_to_new_uzbek_alphabet(category.upper())

        # 3 headline variants
        headline_options = [
            headline,
            convert_to_new_uzbek_alphabet(f"Rasmiy: {headline}"),
            convert_to_new_uzbek_alphabet(f"{category_clean}: {headline}")
        ]

        card_directive = VisualCardDirective(
            template="STANDARD_NEWS_16_9",
            badge_text=category_clean,
            badge_color="#0055FF" if category != "TEZKOR" else "#FF0000",
            headline_for_card=headline[:100],
            image_source_url=media_img,
        )

        return EditorialPackage(
            audit_id=audit_id,
            headline_selected=headline,
            headline_alternatives=headline_options,
            telegram_clean_text=telegram_text,
            character_count=len(telegram_text),
            visual_card_directive=card_directive,
        )

    async def _llm_craft(
        self, audit_id: str, title: str, clean_body: str, category: str, media_img: Optional[str]
    ) -> EditorialPackage:
        """LLM-assisted professional copywriting using Google Gemini."""
        from google import genai
        client = genai.Client(api_key=self.gemini_key)

        prompt = f"""
Sen ROVON.UZ ning yetakchi Bosh Muharriri (AI-3: EDITOR)san.
Taqdim etilgan tasdiqlangan faktlar asosida Telegram kanali uchun yuqori darajadagi professional yangilik tayyorla.

QAT'IY QOIDALAR:
1. ZERO DISTORTION: Birorta raqam, ism, joy yoki sanani O'ZGARTIRMA, yangi fakt to'qima.
2. YANGI O'ZBEK LOTIN ALIFBOSI (2026): Barcha matnlarni qat'iy ravishda Yangi Lotin alifbosida (Ö ö, Ğ ğ, Ş ş, Ç ç) yoz. Eskirgan Sh, Ch, O', G' larni umuman ishlatma!
3. STRUKTURA: 
   - headline_selected: Aniq, lo'nda va nufuzli sarlavha (hech qanday emojisiz, max 90 belgi).
   - telegram_clean_text: 2-3 ta tushunarli abzats. Ichida sarlavhani takrorlama! Faqat yangilik mazmuni. Oxirgi qatorda "🔗 @rovonuz — Tezkor va ishonchli axborot" bo'lsin.
   - Hech qanday emoji spam (masalan: 😎 yoki ❗️ ketma-ketligi) yoki kanal heshteglari qo'shma.
4. headline_alternatives: 3 ta sifatli sarlavha varianti.

Sarlavha: {title}
Kategoriya: {category}
Faktlar matni: {clean_body}

Javobni faqat toza JSON formatida qaytar:
{{
  "headline_selected": "...",
  "headline_alternatives": ["...", "...", "..."],
  "telegram_clean_text": "...",
  "badge_text": "{category.upper()}",
  "headline_for_card": "..."
}}
"""
        response = client.models.generate_content(
            model=settings.GEMINI_EDITORIAL_MODEL,
            contents=prompt,
        )
        raw_json = re.search(r'\{.*\}', response.text, re.DOTALL)
        if raw_json:
            data = json.loads(raw_json.group(0))
            headline = convert_to_new_uzbek_alphabet(data.get("headline_selected", title).strip())
            headline_for_card = convert_to_new_uzbek_alphabet(data.get("headline_for_card", headline[:90]).strip())
            clean_text = convert_to_new_uzbek_alphabet(data.get("telegram_clean_text", "").strip())
            badge = convert_to_new_uzbek_alphabet(data.get("badge_text", category.upper()).strip())
            alts = [convert_to_new_uzbek_alphabet(a) for a in data.get("headline_alternatives", [headline])]

            card_directive = VisualCardDirective(
                template="STANDARD_NEWS_16_9",
                badge_text=badge,
                badge_color="#0055FF",
                headline_for_card=headline_for_card,
                image_source_url=media_img,
            )
            return EditorialPackage(
                audit_id=audit_id,
                headline_selected=headline,
                headline_alternatives=alts,
                telegram_clean_text=clean_text,
                character_count=len(clean_text),
                visual_card_directive=card_directive,
            )

        return self._deterministic_craft(audit_id, title, clean_body, category, media_img)
