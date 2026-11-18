"""
ROVON.UZ - Database Uzbek Language Enforcer & Translator
Audits all existing queue items and editorial packages in rovon_media.db.
Translates any Russian text into natural Uzbek in the 2026 New Uzbek Latin Alphabet (Ö, Ğ, Ş, Ç).
"""

import asyncio
import os
from datetime import datetime, timezone
from sqlalchemy import select
from app.db.session import AsyncSessionLocal
from app.db.models import AI3Editorial, AI4PublishingQueue
from app.ingestion.sanitizer import (
    is_russian_text,
    translate_to_uzbek,
    convert_to_new_uzbek_alphabet,
)
from app.media_studio.canvas_generator import canvas_generator


async def clean_database():
    print("=" * 60)
    print("ROVON.UZ - DATABASE UZBEK LANGUAGE AUDIT & TRANSLATION")
    print("=" * 60)

    async with AsyncSessionLocal() as session:
        # 1. Fetch all editorials
        stmt = select(AI3Editorial)
        editorials = (await session.execute(stmt)).scalars().all()
        print(f"Total editorial records in DB: {len(editorials)}")

        translated_count = 0
        now = datetime.now(timezone.utc)

        for ed in editorials:
            hl = (ed.headline_selected or "").strip()
            body = (ed.telegram_clean_text or "").strip()

            needs_translation = (
                is_russian_text(hl)
                or is_russian_text(body)
                or "ы" in hl.lower()
                or "ы" in body.lower()
                or "dlya" in hl.lower()
                or "dlya" in body.lower()
                or "kofeynya" in hl.lower()
            )

            if needs_translation:
                print(f"\n[Translating] ID: {ed.id}")
                print(f"  Old Russian HL: {hl[:70]}")
                uz_hl = translate_to_uzbek(hl)
                uz_body = translate_to_uzbek(body)

                clean_hl = convert_to_new_uzbek_alphabet(uz_hl)
                clean_body = convert_to_new_uzbek_alphabet(uz_body)

                print(f"  New Uzbek HL:   {clean_hl[:70]}")

                ed.headline_selected = clean_hl
                ed.telegram_clean_text = clean_body

                # Regenerate visual card in New Uzbek Latin
                os.makedirs("storage/cards", exist_ok=True)
                card_filename = f"storage/cards/ed_{ed.id}_{int(now.timestamp())}.jpg"
                try:
                    card_path = canvas_generator.generate_news_card(
                        headline=clean_hl,
                        summary_text=clean_body,
                        badge_text=convert_to_new_uzbek_alphabet(ed.card_badge_text or "YANGILIK"),
                        output_path=card_filename
                    )
                    ed.generated_card_url = card_path
                except Exception as e:
                    print(f"  Card generation warning: {e}")

                translated_count += 1
            else:
                # Still enforce 2026 New Uzbek Latin Alphabet
                ed.headline_selected = convert_to_new_uzbek_alphabet(hl)
                ed.telegram_clean_text = convert_to_new_uzbek_alphabet(body)

        await session.commit()
        print(f"\n✅ Successfully audited all records! Translated: {translated_count} Russian items to New Uzbek Latin.")


if __name__ == "__main__":
    asyncio.run(clean_database())
