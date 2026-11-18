"""
ROVON.UZ - Instagram Public Web Harvester
Harvests public announcements and captions from official government/agency Instagram profiles.
"""

import asyncio
import re
from datetime import datetime, timezone
from typing import Dict, List, Optional
import httpx
from bs4 import BeautifulSoup

from app.ingestion.sanitizer import prepare_article_text


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,uz;q=0.8",
}


class InstagramPublicScraper:
    """
    Harvester for public Instagram profiles of government agencies and spokespersons.
    Designed with rate-limit evasion and resilient parsing.
    """

    def __init__(self, timeout: float = 4.0):
        self.timeout = timeout

    async def fetch_profile_posts(self, username: str, limit: int = 5) -> List[Dict]:
        """
        Fetches the latest public posts from an Instagram profile.
        """
        clean_user = username.lstrip("@").strip()
        url = f"https://www.instagram.com/{clean_user}/"

        async with httpx.AsyncClient(headers=DEFAULT_HEADERS, timeout=self.timeout, follow_redirects=True) as client:
            try:
                response = await client.get(url)
                if response.status_code != 200:
                    return []

                # Extract shared data or meta tags
                soup = BeautifulSoup(response.text, "html.parser")
                meta_desc = soup.find("meta", property="og:description")
                meta_image = soup.find("meta", property="og:image")

                if not meta_desc:
                    return []

                caption = meta_desc.get("content", "").strip()
                if not caption or len(caption) < 40:
                    return []

                image_url = meta_image.get("content") if meta_image else None
                media_urls = [image_url] if image_url else []

                title = caption.split("\n")[0][:150]
                clean_text, content_hash = prepare_article_text(caption, title)

                return [{
                    "source_url": url,
                    "source_identifier": f"@{clean_user}",
                    "source_type": "INSTAGRAM_PUBLIC",
                    "title": title,
                    "body_raw": caption,
                    "body_clean": clean_text,
                    "content_hash": content_hash,
                    "media_urls": media_urls,
                    "published_at": datetime.now(timezone.utc),
                }]

            except Exception as e:
                print(f"[InstagramScraper Error] @{clean_user}: {e}")
                return []
