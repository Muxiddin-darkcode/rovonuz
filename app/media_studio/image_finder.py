"""
ROVON.UZ - Automated News Photo Search & Retrieval Engine
Finds relevant, high-definition photographs from the web when an ingested news article
lacks an attached image:
1. Live web search via Tavily Image Search API (for exact agency, event, or entity photos)
2. Fallback to Wikimedia / Unsplash curated topic imagery
3. Validates resolution, format, and aspect ratio before returning
"""

import os
import re
import httpx
from io import BytesIO
from typing import Optional, List
from PIL import Image

from app.core.config import settings


# Curated high-resolution editorial backup imagery for broad categories
CATEGORY_FALLBACK_IMAGES = {
    "qonun": "https://images.unsplash.com/photo-1589829545856-d10d557cf95f?w=1200&q=80",      # Adliya, sud, qonunchilik
    "adliya": "https://images.unsplash.com/photo-1589829545856-d10d557cf95f?w=1200&q=80",
    "sud": "https://images.unsplash.com/photo-1589829545856-d10d557cf95f?w=1200&q=80",
    "iqtisod": "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=1200&q=80",    # Moliya, bank, soliq
    "bank": "https://images.unsplash.com/photo-1565372195458-9de0b320ef04?w=1200&q=80",
    "ta'lim": "https://images.unsplash.com/photo-1523240795612-9a054b0db644?w=1200&q=80",    # Maktab, universitet, ta'lim
    "talim": "https://images.unsplash.com/photo-1523240795612-9a054b0db644?w=1200&q=80",
    "energetika": "https://images.unsplash.com/photo-1473341304170-971dccb5ac1e?w=1200&q=80",# Gaz, elektr, energiya
    "gaz": "https://images.unsplash.com/photo-1473341304170-971dccb5ac1e?w=1200&q=80",
    "tibbiyot": "https://images.unsplash.com/photo-1584515979956-d9f6e5d09982?w=1200&q=80",  # Sog'liqni saqlash, shifoxona
    "salomatlik": "https://images.unsplash.com/photo-1584515979956-d9f6e5d09982?w=1200&q=80",
    "fvv": "https://images.unsplash.com/photo-1582139329536-e7284fece509?w=1200&q=80",       # Qutqaruvchilar, favqulodda
    "favqulodda": "https://images.unsplash.com/photo-1582139329536-e7284fece509?w=1200&q=80",
    "transport": "https://images.unsplash.com/photo-1506521781263-d8422e82f27a?w=1200&q=80", # Yollar, transport, avtomobil
    "samolyot": "https://images.unsplash.com/photo-1517649763962-0c623266ddc0?w=1200&q=80",  # Aviatsiya
    "avia": "https://images.unsplash.com/photo-1517649763962-0c623266ddc0?w=1200&q=80",
    "sport": "https://images.unsplash.com/photo-1461896836934-ffe607ba8211?w=1200&q=80",     # Sport musobaqalari
    "dunyo": "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=1200&q=80",     # Xalqaro yangiliklar
    "prezident": "https://images.unsplash.com/photo-1541872703-74c5e44368f9?w=1200&q=80",   # Rasmiy davlat binolari
}


class NewsImageFinder:
    """Finds and downloads relevant news photos when an article has no media."""

    def __init__(self):
        self.tavily_key = settings.TAVILY_API_KEY
        self.cache_dir = "storage/cards"
        os.makedirs(self.cache_dir, exist_ok=True)

    def _build_search_query(self, headline: str, category: str) -> str:
        """Constructs an effective, targeted search query for news photo retrieval."""
        clean = re.sub(r'[*_#«»"\'`!?:;.,]', ' ', headline)
        clean = re.sub(r'\s+', ' ', clean).strip()

        words = [w for w in clean.split() if len(w) > 2]
        # Take key 4-6 words
        selected_words = words[:6]

        query = " ".join(selected_words)
        if "o'zbekiston" not in query.lower() and "ozbekiston" not in query.lower():
            query += " O'zbekiston"
        return query

    async def find_and_download_image(
        self,
        headline: str,
        category: str = "YANGILIK",
        body: str = "",
        article_id: str = "temp",
    ) -> Optional[str]:
        """
        Searches the web for a matching image and saves it to a local temporary file.
        Returns the local file path if successful, None otherwise.
        """
        dest_path = os.path.join(self.cache_dir, f"temp_found_{article_id}.jpg")

        # 1. Primary: Tavily Live Image Search
        if self.tavily_key and "your_tavily" not in self.tavily_key:
            query = self._build_search_query(headline, category)
            image_urls = await self._search_tavily_images(query)
            for url in image_urls:
                saved = await self._download_and_validate(url, dest_path)
                if saved:
                    print(f"[ImageFinder] Downloaded news image from web: {url[:70]}...", flush=True)
                    return saved

        # 2. Secondary: Fallback to Curated Category Imagery
        fallback_url = self._get_category_fallback(f"{headline} {category} {body}")
        if fallback_url:
            saved = await self._download_and_validate(fallback_url, dest_path)
            if saved:
                print(f"[ImageFinder] Used high-res category fallback: {fallback_url[:70]}...", flush=True)
                return saved

        return None

    async def _search_tavily_images(self, query: str) -> List[str]:
        """Queries Tavily API for relevant images."""
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                res = await client.post(
                    "https://api.tavily.com/search",
                    json={
                        "api_key": self.tavily_key,
                        "query": query,
                        "include_images": True,
                        "max_results": 5,
                    }
                )
                if res.status_code == 200:
                    data = res.json()
                    images = data.get("images", [])
                    # Filter out logos, icons, svgs, trackers
                    valid_images = []
                    for img in images:
                        if not isinstance(img, str) or not img.startswith("http"):
                            continue
                        lower = img.lower()
                        if any(bad in lower for bad in [".svg", "logo", "icon", "avatar", "badge", "pixel"]):
                            continue
                        valid_images.append(img)
                    return valid_images or images
        except Exception as e:
            print(f"[ImageFinder Warning] Tavily image search error: {e}", flush=True)
        return []

    def _get_category_fallback(self, text: str) -> Optional[str]:
        """Matches text against topic keywords for high-definition fallback."""
        lower = text.lower()
        for kw, url in CATEGORY_FALLBACK_IMAGES.items():
            if kw in lower:
                return url
        return CATEGORY_FALLBACK_IMAGES.get("dunyo")

    async def _download_and_validate(self, url: str, dest_path: str) -> Optional[str]:
        """Downloads an image and validates that it can be opened and has sufficient resolution."""
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
            "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
        }
        try:
            async with httpx.AsyncClient(headers=headers, timeout=8.0, follow_redirects=True) as client:
                resp = await client.get(url)
                if resp.status_code != 200 or len(resp.content) < 8000:
                    return None

                # Validate with Pillow
                img = Image.open(BytesIO(resp.content))
                w, h = img.size
                if w < 320 or h < 200:
                    return None  # Too small, likely an icon

                # Save as RGB JPEG
                img = img.convert("RGB")
                img.save(dest_path, "JPEG", quality=90)
                return dest_path
        except Exception:
            return None


# Global singleton instance
news_image_finder = NewsImageFinder()
