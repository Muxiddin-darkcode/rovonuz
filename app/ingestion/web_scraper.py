"""
ROVON.UZ - Web Scraper & RSS Ingestion Engine
Extracts clean news articles from news websites and government portals.
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional
import httpx
import trafilatura
from bs4 import BeautifulSoup
import feedparser

from app.ingestion.sanitizer import prepare_article_full, prepare_article_text


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36 ROVON-NewsBot/3.1"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "uz,ru,en;q=0.9",
}


class WebScraper:
    """Async scraper for websites and RSS feeds."""

    def __init__(self, timeout: float = 15.0):
        self.timeout = timeout

    async def fetch_article(self, url: str) -> Optional[Dict]:
        """
        Fetches a web page and extracts structured article text using Trafilatura.
        """
        async with httpx.AsyncClient(headers=DEFAULT_HEADERS, timeout=self.timeout, follow_redirects=True) as client:
            try:
                response = await client.get(url)
                if response.status_code != 200:
                    return None

                html_content = response.text
                
                # Extract clean article using Trafilatura
                extracted_json = trafilatura.extract(
                    html_content,
                    output_format="json",
                    include_links=False,
                    include_images=True,
                    with_metadata=True
                )
                
                if not extracted_json:
                    # Fallback to BeautifulSoup if Trafilatura fails
                    return self._fallback_bs4_extract(url, html_content)

                import json
                data = json.loads(extracted_json)
                
                raw_text = data.get("text", "")
                title = data.get("title", "")
                
                if not raw_text or len(raw_text) < 100:
                    return None

                clean_text, content_hash = prepare_article_text(raw_text, title)

                images = []
                if data.get("image"):
                    images.append(data["image"])

                published_at = None
                date_str = data.get("date")
                if date_str:
                    try:
                        from dateutil.parser import parse
                        published_at = parse(date_str)
                    except Exception:
                        published_at = datetime.now(timezone.utc)
                else:
                    published_at = datetime.now(timezone.utc)

                return {
                    "source_url": url,
                    "source_identifier": url.split("//")[-1].split("/")[0],
                    "source_type": "WEB_SCRAPER",
                    "title": title,
                    "body_raw": raw_text,
                    "body_clean": clean_text,
                    "content_hash": content_hash,
                    "media_urls": images,
                    "published_at": published_at,
                }

            except Exception as e:
                print(f"[WebScraper Error] {url}: {e}")
                return None

    def _fallback_bs4_extract(self, url: str, html: str) -> Optional[Dict]:
        """Simple fallback extraction using BeautifulSoup."""
        soup = BeautifulSoup(html, "html.parser")
        title_el = soup.find("h1") or soup.find("title")
        title = title_el.get_text().strip() if title_el else ""

        paragraphs = soup.find_all("p")
        text = "\n\n".join([p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 30])
        
        if not text or len(text) < 100:
            return None

        clean_text, content_hash = prepare_article_text(text, title)

        return {
            "source_url": url,
            "source_identifier": url.split("//")[-1].split("/")[0],
            "source_type": "WEB_SCRAPER",
            "title": title,
            "body_raw": text,
            "body_clean": clean_text,
            "content_hash": content_hash,
            "media_urls": [],
            "published_at": datetime.now(timezone.utc),
        }

    async def fetch_rss_feed(self, feed_url: str) -> List[Dict]:
        """
        Fetches an RSS/Atom feed and parses new article entries.
        """
        async with httpx.AsyncClient(headers=DEFAULT_HEADERS, timeout=self.timeout, follow_redirects=True) as client:
            try:
                response = await client.get(feed_url)
                if response.status_code != 200:
                    return []

                feed = feedparser.parse(response.text)
                articles = []

                for entry in feed.entries[:10]:  # Limit to 10 latest entries per run
                    url = entry.get("link")
                    if not url:
                        continue
                    
                    title = entry.get("title", "")
                    raw_text = entry.get("summary") or entry.get("description") or ""

                    # Clean summary
                    soup = BeautifulSoup(raw_text, "html.parser")
                    raw_text = soup.get_text().strip()

                    clean_title, clean_text, content_hash = prepare_article_full(f"{title}\n{raw_text}", title)

                    # Extract images from enclosures & media_content
                    media_urls = []
                    if "enclosures" in entry:
                        for enc in entry.get("enclosures", []):
                            href = enc.get("href")
                            if href and any(ext in href.lower() for ext in [".jpg", ".jpeg", ".png", ".webp"]):
                                media_urls.append(href)
                    if "media_content" in entry:
                        for mc in entry.get("media_content", []):
                            u = mc.get("url")
                            if u and u not in media_urls:
                                media_urls.append(u)

                    articles.append({
                        "source_url": url,
                        "source_identifier": url.split("//")[-1].split("/")[0],
                        "source_type": "WEB_RSS",
                        "title": clean_title,
                        "body_raw": raw_text,
                        "body_clean": clean_text,
                        "content_hash": content_hash,
                        "media_urls": media_urls,
                        "published_at": datetime.now(timezone.utc),
                    })

                return articles
            except Exception as e:
                print(f"[RSS Error] {feed_url}: {e}")
                return []
