"""
ROVON.UZ - Live Telegram Web Scraper Test
Fetches real posts from official public channel @huquqiyaxborot
"""

import asyncio
from app.ingestion.telegram_scraper import TelegramWebScraper


async def test_live_scrape():
    print("Testing live Telegram web preview on @huquqiyaxborot...")
    scraper = TelegramWebScraper()
    posts = await scraper.fetch_channel_posts("@huquqiyaxborot", limit=3)
    
    print(f"Fetched {len(posts)} posts from @huquqiyaxborot:")
    for i, post in enumerate(posts, 1):
        print(f"\n--- Post {i} ---")
        print(f"Title: {post['title']}")
        print(f"URL: {post['source_url']}")
        print(f"Source: {post['source_identifier']}")
        print(f"Clean snippet: {post['body_clean'][:120]}...")
        print(f"Photos: {len(post['media_urls'])}")
        print(f"Published: {post['published_at']}")

    assert len(posts) > 0, "No posts could be fetched from public channel!"
    print("\n✅ Live Telegram Web Ingestion is 100% OPERATIONAL!")


if __name__ == "__main__":
    asyncio.run(test_live_scrape())
