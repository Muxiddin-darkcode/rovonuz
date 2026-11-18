"""
ROVON.UZ - End-to-End Pipeline Unit & Verification Tests
Tests Sanitization, 4-AI Brain Cluster, and Canvas Generation.
"""

import os
import asyncio
from datetime import datetime, timezone

from app.ingestion.sanitizer import (
    transliterate_cyrillic_to_latin,
    sanitize_text,
    prepare_article_text,
)
from app.ai_brain.ai1_investigator.investigator import RovonInvestigator
from app.ai_brain.ai2_auditor.auditor import RovonAuditor
from app.ai_brain.ai3_editor.editor import RovonEditor
from app.ai_brain.ai4_strategist.strategist import RovonStrategist
from app.media_studio.canvas_generator import CanvasGenerator


def test_sanitizer():
    print("\n--- 1. Testing Sanitizer & Transliteration ---")
    cyrillic_sample = "Тошкент метрополитенида янги йўналиш қурилиши бошланди. Бизнинг каналга обуна бўлинг: @fvv_bot"
    latin = transliterate_cyrillic_to_latin(cyrillic_sample)
    cleaned, c_hash = prepare_article_text(cyrillic_sample, "Янги метро")

    print(f"Original: {cyrillic_sample}")
    print(f"Transliterated & Cleaned: {cleaned}")
    print(f"Content Hash (SHA-256): {c_hash}")

    assert "fvv_bot" not in cleaned, "Ad pattern was not removed!"
    assert "Toşkent" in cleaned, "Transliteration failed!"
    print("✅ Sanitizer Test Passed!")


async def test_4_ai_cluster():
    print("\n--- 2. Testing 4-AI Brain Cluster ---")
    investigator = RovonInvestigator()
    auditor = RovonAuditor()
    editor = RovonEditor()
    strategist = RovonStrategist()

    sample_article = {
        "id": "11111111-2222-3333-4444-555555555555",
        "title": "Toshkentda 12 ta yangi elektrobus harakati yo'lga qo'yildi",
        "body_clean": "Toshkent shahrida jamoat transportini yaxshilash maqsadida 12 ta yangi elektrobus liniyaga chiqarildi. Transport vazirligi xabariga ko'ra, keyingi oyda yana 50 ta avtobus olib kelinadi.",
        "source_identifier": "@iivuz",
        "source_url": "https://t.me/iivuz/1050",
        "category": "TRANSPORT",
    }

    # AI-1: Investigation
    print("\n[AI-1: INVESTIGATOR] Running claim extraction...")
    inv = await investigator.investigate_article(sample_article)
    print(f"Claims Found: {len(inv.claims)}")
    print(f"Primary Authority: {inv.primary_source_authority}")
    assert inv.primary_source_authority >= 0.95, "Official source authority mismatch!"

    # AI-2: Audit
    print("\n[AI-2: AUDITOR] Running Bayesian verification & risk check...")
    audit = await auditor.audit_investigation(inv, sample_article["body_clean"])
    print(f"Verdict: {audit.verdict}")
    print(f"Bayesian Score: {audit.bayesian_score}")
    print(f"Risk Tier: {audit.risk_tier}")
    print(f"Human Gate Required: {audit.human_gate_required}")
    assert audit.verdict in ["VERIFIED", "MOSTLY_VERIFIED"], "Verification failed!"

    # AI-3: Editorial
    print("\n[AI-3: EDITOR] Styling post for Telegram...")
    editorial = await editor.craft_editorial_package(
        audit=audit,
        title=sample_article["title"],
        clean_body=sample_article["body_clean"],
        category=sample_article["category"],
    )
    print(f"Selected Headline: {editorial.headline_selected}")
    print(f"Telegram Text Length: {editorial.character_count} chars")
    print(f"Headline Variants: {editorial.headline_alternatives}")
    assert len(editorial.headline_alternatives) >= 2, "Headline options missing!"

    # AI-4: Strategist
    print("\n[AI-4: STRATEGIST] Optimizing schedule & priority...")
    schedule = await strategist.schedule_editorial(
        editorial=editorial,
        category=sample_article["category"],
        published_at=datetime.now(timezone.utc),
    )
    print(f"Hawkes Score: {schedule.hawkes_priority_score}")
    print(f"Priority Tier: {schedule.priority_tier}")
    print(f"Scheduled Slot: {schedule.scheduled_slot}")
    print(f"Idempotency Key: {schedule.idempotency_key[:16]}...")
    assert schedule.idempotency_key, "Idempotency key generation failed!"

    print("✅ 4-AI Brain Cluster Pipeline Passed!")
    return editorial


def test_canvas():
    print("\n--- 3. Testing Pillow 16:9 Canvas Generator ---")
    canvas = CanvasGenerator()
    out_file = "storage/cards/test_sample_card.jpg"
    res = canvas.generate_news_card(
        headline="Toshkentda 12 ta yangi elektrobus yo'nalishga chiqarildi",
        badge_text="TRANSPORT",
        badge_color="#0055FF",
        output_path=out_file,
    )
    print(f"Generated Card Path: {res}")
    assert os.path.exists(res), "Card image was not created!"
    print(f"File Size: {os.path.getsize(res)} bytes")
    print("✅ Canvas Generator Test Passed!")


async def main():
    test_sanitizer()
    await test_4_ai_cluster()
    test_canvas()
    print("\n🎉 ALL PHASE 1 CORE TESTS PASSED SUCCESSFULLY!")


if __name__ == "__main__":
    asyncio.run(main())
