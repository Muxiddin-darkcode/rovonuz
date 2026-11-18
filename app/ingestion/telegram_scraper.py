"""
ROVON.UZ - Telegram Ingestion Engine
Scrapes official public channels via Web Preview (zero-credential fallback)
and Telethon MTProto (zero-latency real-time ingestion).
"""

import re
from datetime import datetime, timezone
from typing import Dict, List, Optional
import httpx
from bs4 import BeautifulSoup

from app.ingestion.sanitizer import prepare_article_full, prepare_article_text
from app.core.config import settings


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36 ROVON-NewsBot/3.1"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


class TelegramWebScraper:
    """
    Scrapes Telegram public channels via the public web preview endpoint:
    https://t.me/s/{channel_username}
    Requires no phone number or API keys, completely safe and resilient.
    """

    def __init__(self, timeout: float = 12.0):
        self.timeout = timeout

    async def fetch_channel_posts(self, channel_username: str, limit: int = 10) -> List[Dict]:
        """
        Fetches the latest posts from a public Telegram channel.
        channel_username can be with or without '@'.
        """
        username = channel_username.lstrip("@").strip()
        url = f"https://t.me/s/{username}"

        async with httpx.AsyncClient(headers=DEFAULT_HEADERS, timeout=self.timeout, follow_redirects=True) as client:
            try:
                response = await client.get(url)
                if response.status_code != 200:
                    return []

                soup = BeautifulSoup(response.text, "html.parser")
                messages = soup.find_all("div", class_="tgme_widget_message_wrap")

                results = []
                for msg_wrap in messages[-limit:]:
                    msg = msg_wrap.find("div", class_="tgme_widget_message")
                    if not msg:
                        continue

                    # Extract post ID / URL
                    post_id_raw = msg.get("data-post")  # e.g. "fvv_uz/12450"
                    if not post_id_raw:
                        continue
                    post_url = f"https://t.me/{post_id_raw}"

                    # Extract text content
                    text_div = msg.find("div", class_="tgme_widget_message_text")
                    if not text_div:
                        continue  # Skip media without text

                    raw_text = text_div.get_text(separator="\n").strip()
                    if not raw_text or len(raw_text) < 40:
                        continue

                    # Clean raw Telegram text and extract proper headline (no emojis, no channel headers)
                    clean_title, clean_text, content_hash = prepare_article_full(raw_text)

                    # Extract photo URLs if available
                    media_urls = []
                    photo_wrap = msg.find("a", class_="tgme_widget_message_photo_wrap")
                    if photo_wrap and photo_wrap.get("style"):
                        style = photo_wrap.get("style", "")
                        match = re.search(r"background-image:url\('([^']+)'\)", style)
                        if match:
                            media_urls.append(match.group(1))

                    # Extract timestamp
                    published_at = datetime.now(timezone.utc)
                    time_tag = msg.find("time")
                    if time_tag and time_tag.get("datetime"):
                        try:
                            from dateutil.parser import parse
                            published_at = parse(time_tag["datetime"])
                        except Exception:
                            pass

                    results.append({
                        "source_url": post_url,
                        "source_identifier": f"@{username}",
                        "source_type": "TELEGRAM_CHANNEL",
                        "title": clean_title[:200],
                        "body_raw": raw_text,
                        "body_clean": clean_text,
                        "content_hash": content_hash,
                        "media_urls": media_urls,
                        "published_at": published_at,
                    })

                return results

            except Exception as e:
                print(f"[TelegramScraper Error] @{username}: {e}")
                return []
