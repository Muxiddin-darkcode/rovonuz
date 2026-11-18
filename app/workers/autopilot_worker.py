"""
ROVON.UZ - Autonomous Background Auto-Pilot & Auto-Publisher Engine
Multi-Platform Harvester for the TOP 40 OFFICIAL SOURCES:
- 20 Official Telegram Government & Ministry Channels
- 12 Leading National News Portals & RSS Feeds
- 8 Official Government & Media Instagram Profiles
Processes all ingested news through the 4-AI newsroom and automatically publishes to @rovonuz.
"""

import os
import re
import asyncio
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional
from sqlalchemy.future import select

from app.core.config import settings
from app.ingestion.telegram_scraper import TelegramWebScraper
from app.ingestion.web_scraper import WebScraper
from app.ingestion.instagram_scraper import InstagramPublicScraper
from app.workers.orchestrator import PipelineOrchestrator
import app.core.state as system_state


# ==============================================================================
# TOP 40 OFFICIAL AUTHORITATIVE SOURCES IN UZBEKISTAN
# ==============================================================================
TOP_40_SOURCES = {
    # 1. 20 Official Telegram Channels (Davlat va Rasmiy Idoralar)
    "telegram": [
        "@huquqiyaxborot",            # 1. Adliya vazirligi (Qonunchilik xabarlari)
        "@pressuz",                   # 2. O'zbekiston Prezidenti matbuot xizmati
        "@fvv_uz",                    # 3. Favqulodda vaziyatlar vazirligi (FVV)
        "@iivuz",                     # 4. Ichki ishlar vazirligi (IIV)
        "@ssvuz",                     # 5. Sog'liqni saqlash vazirligi (SSV)
        "@toshkent_shahar_hokimligi", # 6. Toshkent shahar hokimligi
        "@boshprokuratura",           # 7. Bosh prokuratura
        "@bojxona_qomitasi",          # 8. Davlat Bojxona qo'mitasi
        "@statistika_rasmiy",         # 9. O'zbekiston Statistika agentligi
        "@soliqplusuz",               # 10. Davlat Soliq qo'mitasi
        "@markaziybankuz",            # 11. O'zbekiston Markaziy banki
        "@eduuz",                     # 12. Oliy ta'lim, fan va innovatsiyalar vazirligi
        "@uztdi",                     # 13. Maktabgacha va maktab ta'limi vazirligi
        "@mfa_uzbekistan",            # 14. Tashqi ishlar vazirligi (TIV)
        "@mudofaa_press",             # 15. Mudofaa vazirligi
        "@adliya_uz",                 # 16. Adliya vazirligi bosh axborot kanali
        "@antimonopol_uz",            # 17. Raqobatni rivojlantirish qo'mitasi
        "@energetika_vazirligi",      # 18. Energetika vazirligi
        "@uzagmgov",                  # 19. Tog'-kon sanoati va geologiya vazirligi
        "@koronavirusinfouz",         # 20. Rasmiy tezkor shtab
    ],
    # 2. 12 Leading News Websites & RSS Portals (Veb-saytlar va RSS tasmalari)
    "web_rss": [
        "https://daryo.uz/rss",                                # 21. Daryo.uz (O'zbekiston va dunyo)
        "https://kun.uz/news/rss",                             # 22. Kun.uz (Tezkor yangiliklar)
        "https://www.gazeta.uz/uz/rss/",                       # 23. Gazeta.uz (Tahliliy va rasmiy)
        "https://uza.uz/uz/rss",                               # 24. O'zA (Milliy axborot agentligi)
        "https://qalampir.uz/uz/rss",                          # 25. Qalampir.uz
        "https://xabar.uz/rss",                                # 26. Xabar.uz (AKT va jamiyat)
        "https://aniq.uz/uz/rss",                              # 27. Aniq.uz (Tezkor yangiliklar)
        "https://yuz.uz/rss",                                  # 28. Yangi O'zbekiston
        "https://oz.sputniknews.uz/export/rss2/archive/index.xml", # 29. Sputnik O'zbekiston (O'zbekcha)
        "https://anhor.uz/uz/feed/",                           # 30. Anhor.uz (O'zbekcha lenta)
        "https://president.uz/uz",                             # 31. O'zbekiston Prezidenti portali
        "https://gov.uz/uz",                                   # 32. O'zbekiston Hukumati portali
    ],
    # 3. 8 Official Instagram Profiles
    "instagram": [
        "mirziyoyev_sh",       # 33. Shavkat Mirziyoyev rasmiy sahifasi
        "adliya_vazirligi",    # 34. Adliya vazirligi
        "fvv_uz",              # 35. Favqulodda vaziyatlar vazirligi
        "iiv.uz",              # 36. Ichki ishlar vazirligi
        "ssv.uz",              # 37. Sog'liqni saqlash vazirligi
        "tashkent_hokimiyat",  # 38. Toshkent shahar hokimligi
        "kun.uz",              # 39. Kun.uz rasmiy Instagram
        "daryo.rasmiy",        # 40. Daryo.uz rasmiy Instagram
    ]
}


class AutoPilotWorker:
    """Manages continuous background ingestion from 40 sources and autonomous publishing."""

    def __init__(self):
        self.is_active: bool = False
        self.scan_interval_seconds: int = 150  # Scan every 2.5 minutes
        self.publish_interval_seconds: int = 600  # Exactly 10 minutes (600 seconds)
        self.auto_publish_enabled: bool = True

        self.telegram_channels: List[str] = TOP_40_SOURCES["telegram"]
        self.web_rss_sources: List[str] = TOP_40_SOURCES["web_rss"]
        self.instagram_sources: List[str] = TOP_40_SOURCES["instagram"]

        # Rotation pointers to distribute load gracefully
        self._tg_idx: int = 0
        self._web_idx: int = 0
        self._ig_idx: int = 0

        self.last_scan_at: Optional[datetime] = None
        self.total_scanned_articles: int = 0
        self.total_scheduled_articles: int = 0
        self.total_dispatched_articles: int = 0

        self._scanner_task: Optional[asyncio.Task] = None
        self._publisher_task: Optional[asyncio.Task] = None

        self.telegram_scraper = TelegramWebScraper()
        self.web_scraper = WebScraper()
        self.instagram_scraper = InstagramPublicScraper()
        self.orchestrator = PipelineOrchestrator()

    def start(self):
        """Starts the multi-source background scanner and autonomous publisher."""
        self.is_active = True
        if not self._scanner_task or self._scanner_task.done():
            self._scanner_task = asyncio.create_task(self._run_scanner_loop())
            print(f"[AutoPilot] 40-Source background harvester started (Interval: {self.scan_interval_seconds}s).", flush=True)

        if not self._publisher_task or self._publisher_task.done():
            self._publisher_task = asyncio.create_task(self._run_publisher_loop())
            print(f"[AutoPublisher] Autonomous publisher started (Interval: {self.publish_interval_seconds}s).", flush=True)

    def stop(self):
        """Pauses the background workers."""
        self.is_active = False
        if self._scanner_task and not self._scanner_task.done():
            self._scanner_task.cancel()
        if self._publisher_task and not self._publisher_task.done():
            self._publisher_task.cancel()
        print("[AutoPilot & AutoPublisher] Harvester paused.", flush=True)

    def set_interval(self, seconds: int):
        self.publish_interval_seconds = max(60, seconds)
        print(f"[AutoPublisher] Publish interval updated to {self.publish_interval_seconds}s ({self.publish_interval_seconds // 60} min).", flush=True)

    def get_status(self) -> Dict[str, Any]:
        return {
            "is_active": self.is_active,
            "interval_seconds": self.scan_interval_seconds,
            "scan_interval_seconds": self.scan_interval_seconds,
            "publish_interval_seconds": self.publish_interval_seconds,
            "auto_publish_enabled": self.auto_publish_enabled,
            "total_monitored_sources": len(self.telegram_channels) + len(self.web_rss_sources) + len(self.instagram_sources),
            "telegram_count": len(self.telegram_channels),
            "web_rss_count": len(self.web_rss_sources),
            "instagram_count": len(self.instagram_sources),
            "monitored_channels": self.telegram_channels[:4] + [f"+{len(self.telegram_channels)-4} ta kanal", "12 ta web", "8 ta IG"],
            "last_scan_at": self.last_scan_at.isoformat() if self.last_scan_at else None,
            "total_scanned": self.total_scanned_articles,
            "total_scheduled": self.total_scheduled_articles,
            "total_dispatched": self.total_dispatched_articles,
            "killswitch_active": system_state.IS_EMERGENCY_STOP_ACTIVE,
        }

    async def _run_scanner_loop(self):
        """Continuous periodic loop that harvests from rotating batches of 40 sources."""
        while self.is_active:
            try:
                if not system_state.IS_EMERGENCY_STOP_ACTIVE:
                    await self.execute_scan_cycle()
            except Exception as e:
                print(f"[AutoPilot Exception] Harvester error: {e}", flush=True)

            await asyncio.sleep(self.scan_interval_seconds)

    async def _run_publisher_loop(self):
        """Continuous background loop that automatically dispatches due articles to Telegram."""
        while self.is_active:
            try:
                if not system_state.IS_EMERGENCY_STOP_ACTIVE and self.auto_publish_enabled:
                    await self.execute_auto_publish_cycle()
            except Exception as e:
                print(f"[AutoPublisher Exception] Publish cycle error: {e}", flush=True)

            await asyncio.sleep(self.publish_interval_seconds)

    async def execute_scan_cycle(self) -> Dict[str, int]:
        """
        Executes a single multi-source harvesting cycle across:
        1. 5 Telegram channels (rotated)
        2. 3 Web RSS portals (rotated)
        3. 2 Instagram accounts (rotated)
        """
        self.last_scan_at = datetime.now(timezone.utc)
        results = {"scanned": 0, "scheduled": 0, "human_gate": 0, "skipped": 0}

        # 1. Harvest Telegram Batch (5 channels per tick)
        tg_batch = []
        for i in range(5):
            idx = (self._tg_idx + i) % len(self.telegram_channels)
            tg_batch.append(self.telegram_channels[idx])
        self._tg_idx = (self._tg_idx + 5) % len(self.telegram_channels)

        for ch in tg_batch:
            try:
                posts = await self.telegram_scraper.fetch_channel_posts(ch, limit=3)
                for post in posts:
                    await self._process_harvested_post(post, results)
            except Exception as e:
                print(f"[AutoPilot] Error scanning Telegram {ch}: {e}", flush=True)

        # 2. Harvest Web RSS Batch (3 feeds per tick)
        web_batch = []
        for i in range(3):
            idx = (self._web_idx + i) % len(self.web_rss_sources)
            web_batch.append(self.web_rss_sources[idx])
        self._web_idx = (self._web_idx + 3) % len(self.web_rss_sources)

        for feed_url in web_batch:
            try:
                if feed_url.endswith("/uz") or "president.uz" in feed_url or "gov.uz" in feed_url:
                    art = await self.web_scraper.fetch_article(feed_url)
                    if art:
                        await self._process_harvested_post(art, results)
                else:
                    feed_posts = await self.web_scraper.fetch_rss_feed(feed_url)
                    for post in feed_posts[:3]:
                        await self._process_harvested_post(post, results)
            except Exception as e:
                print(f"[AutoPilot] Error scanning Web {feed_url}: {e}", flush=True)

        # 3. Harvest Instagram Batch (2 profiles per tick)
        ig_batch = []
        for i in range(2):
            idx = (self._ig_idx + i) % len(self.instagram_sources)
            ig_batch.append(self.instagram_sources[idx])
        self._ig_idx = (self._ig_idx + 2) % len(self.instagram_sources)

        for user in ig_batch:
            try:
                ig_posts = await self.instagram_scraper.fetch_profile_posts(user, limit=2)
                for post in ig_posts:
                    await self._process_harvested_post(post, results)
            except Exception as e:
                print(f"[AutoPilot] Error scanning Instagram @{user}: {e}", flush=True)

        return results

    async def _process_harvested_post(self, post: Dict[str, Any], results: Dict[str, int]):
        """Runs single post through 4-AI newsroom pipeline."""
        results["scanned"] += 1
        self.total_scanned_articles += 1

        res = await self.orchestrator.ingest_and_process_article(post)
        status = res.get("status")

        if status == "scheduled":
            results["scheduled"] += 1
            self.total_scheduled_articles += 1
        elif status == "human_gate_required":
            results["human_gate"] += 1
            await self._notify_admin_gate(res, post)
        else:
            results["skipped"] += 1

    async def execute_auto_publish_cycle(self) -> bool:
        """
        Autonomously dispatches due articles from the queue to the Telegram channel.
        Zero human intervention needed.
        """
        if system_state.IS_EMERGENCY_STOP_ACTIVE or not self.auto_publish_enabled:
            return False

        from app.db.session import AsyncSessionLocal
        from app.db.models.publishing import AI4PublishingQueue
        from app.db.models.editorial import AI3Editorial

        now = datetime.now(timezone.utc)
        async with AsyncSessionLocal() as session:
            # Select the ABSOLUTE NEWEST waiting post in queue
            stmt = (
                select(AI4PublishingQueue)
                .join(AI3Editorial, AI4PublishingQueue.editorial_id == AI3Editorial.id)
                .filter(AI4PublishingQueue.dispatch_status == "WAITING")
                .order_by(AI3Editorial.created_at.desc())
                .limit(1)
            )
            item = (await session.execute(stmt)).scalars().first()
            if not item:
                return False

            editorial = await session.get(AI3Editorial, item.editorial_id)
            if not editorial:
                item.dispatch_status = "FAILED"
                await session.commit()
                return False

            from app.telegram_gateway.bot_service import bot
            from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
            from aiogram.enums import ParseMode
            from app.ingestion.sanitizer import (
                is_russian_text, translate_to_uzbek, convert_to_new_uzbek_alphabet,
                is_news_worthy, format_telegram_post
            )
            from app.media_studio.canvas_generator import canvas_generator

            headline = (editorial.headline_selected or "").strip()
            body = (editorial.telegram_clean_text or "").strip()

            # 1. Quality Gate: Reject bureaucratic spam, dissertations, tenders, obituaries
            if not is_news_worthy(headline, body):
                print(f"[AutoPublisher Filter] Dropped non-news notice: {headline[:60]}", flush=True)
                item.dispatch_status = "CANCELLED"
                await session.commit()
                return False

            # Ensure 100% natural Uzbek language & 2026 New Uzbek Latin Alphabet
            if is_russian_text(headline):
                headline = translate_to_uzbek(headline)
            if is_russian_text(body):
                body = translate_to_uzbek(body)

            headline = convert_to_new_uzbek_alphabet(headline)
            body = convert_to_new_uzbek_alphabet(body)

            # Professional Kun.uz / Zamon.uz formatting: Zero headline duplication
            post_text = format_telegram_post(headline, body)

            channel_id = settings.TELEGRAM_CHANNEL_ID
            channel_btn = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="🌐 ROVON.UZ | Rasmiy Sahifa", url="https://rovon.uz")]]
            )

            published = False
            card_path = editorial.generated_card_url
            if not card_path or not os.path.exists(card_path) or is_russian_text(editorial.headline_selected):
                os.makedirs("storage/cards", exist_ok=True)
                card_filename = f"storage/cards/pub_{item.id}_{int(now.timestamp())}.jpg"
                try:
                    card_path = canvas_generator.generate_news_card(
                        headline=headline,
                        summary_text=body,
                        badge_text=convert_to_new_uzbek_alphabet(editorial.card_badge_text or "YANGILIK"),
                        output_path=card_filename
                    )
                    editorial.generated_card_url = card_path
                    editorial.headline_selected = headline
                    editorial.telegram_clean_text = body
                    await session.commit()
                except Exception as e:
                    print(f"[AutoPublisher Card Error] {e}")
            try:
                if card_path and os.path.exists(card_path):
                    photo = FSInputFile(card_path)
                    try:
                        await bot.send_photo(
                            chat_id=channel_id,
                            photo=photo,
                            caption=post_text[:1024],
                            parse_mode=ParseMode.MARKDOWN,
                            reply_markup=channel_btn
                        )
                    except Exception:
                        photo = FSInputFile(card_path)
                        await bot.send_photo(
                            chat_id=channel_id,
                            photo=photo,
                            caption=post_text[:1024],
                            parse_mode=None,
                            reply_markup=channel_btn
                        )
                else:
                    try:
                        await bot.send_message(
                            chat_id=channel_id,
                            text=post_text,
                            parse_mode=ParseMode.MARKDOWN,
                            reply_markup=channel_btn,
                            disable_web_page_preview=False
                        )
                    except Exception:
                        await bot.send_message(
                            chat_id=channel_id,
                            text=post_text,
                            parse_mode=None,
                            reply_markup=channel_btn,
                            disable_web_page_preview=False
                        )
                published = True
                self.total_dispatched_articles += 1
                print(f"[AutoPublisher] Published NEWEST post to {channel_id}: '{headline[:60]}...'. Next auto-publish in {self.publish_interval_seconds // 60} minutes.", flush=True)
            except Exception as e:
                print(f"[AutoPublisher Error] Failed sending to {channel_id}: {e}", flush=True)

            if published:
                item.dispatch_status = "DISPATCHED"
                item.dispatched_at = datetime.now(timezone.utc)
                await session.commit()
                return True

        return False

    async def _notify_admin_gate(self, orchestrator_res: Dict[str, Any], raw_post: Dict[str, Any]):
        """Sends an urgent push alert to the Telegram admin with action buttons."""
        from app.telegram_gateway.bot_service import bot
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        from aiogram.enums import ParseMode

        admin_id = settings.TELEGRAM_ADMIN_CHAT_ID
        if not admin_id or not bot:
            return

        article_id = orchestrator_res.get("article_id")
        verdict = orchestrator_res.get("verdict", "UNCONFIRMED")
        risk = orchestrator_res.get("risk", "LEVEL_2_MEDIUM")
        score = orchestrator_res.get("score", 0.5)
        title = raw_post.get("title") or raw_post.get("body_clean", "")[:80] + "..."

        text = (
            "🚨 **INSON TASDIG'I TALAB QILINADI (EDITORIAL GATE)**\n\n"
            f"📌 **Sarlavha:** {title}\n"
            f"▫️ **Manba:** {raw_post.get('source_identifier', 'Noma’lum')}\n"
            f"▫️ **Xulosasi:** `{verdict}`\n"
            f"▫️ **Xavf Darajasi:** `{risk}`\n"
            f"▫️ **Bayes Balli:** `{score:.2f}`\n\n"
            "Ushbu xabar shubhali yoki favqulodda deb topildi. Qaroringizni tanlang:"
        )

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Ma'qullash & Navbatga Qo'yish", callback_data=f"audit:approve_by_art:{article_id}"),
                    InlineKeyboardButton(text="❌ Rad Etish (Arxiv)", callback_data=f"audit:reject_by_art:{article_id}"),
                ],
                [
                    InlineKeyboardButton(text="📋 Nashr Navbatini Ko'rish", callback_data="menu:queue"),
                ]
            ]
        )

        try:
            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=text,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=kb
                )
            except Exception:
                await bot.send_message(
                    chat_id=admin_id,
                    text=text,
                    parse_mode=None,
                    reply_markup=kb
                )
            print(f"[AutoPilot Alert] Sent push alert to admin {admin_id} for article {article_id}.", flush=True)
        except Exception as e:
            print(f"[AutoPilot Alert Error] Could not send alert to admin: {e}", flush=True)


# Global singleton instance
autopilot_service = AutoPilotWorker()
