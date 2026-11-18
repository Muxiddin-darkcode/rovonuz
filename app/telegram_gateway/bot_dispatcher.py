"""
ROVON.UZ - Telegram Bot Dispatcher
Aiogram 3 gateway to dispatch formatted messages and photos to @rovonuz channel.
"""

import asyncio
import re
from typing import Optional
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.exceptions import TelegramRetryAfter, TelegramAPIError
from aiogram.types import FSInputFile, URLInputFile

from app.core.config import settings


class TelegramDispatcher:
    """Dispatches approved news packages to the official Telegram channel."""

    def __init__(self):
        self.token = settings.TELEGRAM_BOT_TOKEN
        self.channel_id = settings.TELEGRAM_CHANNEL_ID
        self._bot: Optional[Bot] = None

    def get_bot(self) -> Optional[Bot]:
        if not self._bot and self.token:
            self._bot = Bot(token=self.token)
        return self._bot

    async def dispatch_post(
        self,
        formatted_text: str,
        image_path: Optional[str] = None,
        image_url: Optional[str] = None,
    ) -> Optional[int]:
        """
        Sends formatted text or photo with caption to the channel.
        Returns the published telegram message_id or None on failure.
        """
        bot = self.get_bot()
        if not bot:
            print("[TelegramDispatcher] Bot token not configured. Skipping live dispatch.")
            return None

        # Maximum retries on FloodWait
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # If image is provided, send as photo with caption
                if image_path:
                    photo = FSInputFile(image_path)
                    try:
                        msg = await bot.send_photo(
                            chat_id=self.channel_id,
                            photo=photo,
                            caption=formatted_text[:1024],
                            parse_mode=ParseMode.HTML,
                        )
                        return msg.message_id
                    except Exception:
                        clean_plain = re.sub(r'<[^>]+>', '', formatted_text)[:1024]
                        photo = FSInputFile(image_path)
                        msg = await bot.send_photo(
                            chat_id=self.channel_id,
                            photo=photo,
                            caption=clean_plain,
                            parse_mode=None,
                        )
                        return msg.message_id
                elif image_url:
                    photo = URLInputFile(image_url)
                    try:
                        msg = await bot.send_photo(
                            chat_id=self.channel_id,
                            photo=photo,
                            caption=formatted_text[:1024],
                            parse_mode=ParseMode.HTML,
                        )
                        return msg.message_id
                    except Exception:
                        clean_plain = re.sub(r'<[^>]+>', '', formatted_text)[:1024]
                        photo = URLInputFile(image_url)
                        msg = await bot.send_photo(
                            chat_id=self.channel_id,
                            photo=photo,
                            caption=clean_plain,
                            parse_mode=None,
                        )
                        return msg.message_id
                else:
                    # Text only message
                    try:
                        msg = await bot.send_message(
                            chat_id=self.channel_id,
                            text=formatted_text[:4096],
                            parse_mode=ParseMode.HTML,
                            disable_web_page_preview=False,
                        )
                        return msg.message_id
                    except Exception:
                        clean_plain = re.sub(r'<[^>]+>', '', formatted_text)[:4096]
                        msg = await bot.send_message(
                            chat_id=self.channel_id,
                            text=clean_plain,
                            parse_mode=None,
                            disable_web_page_preview=False,
                        )
                        return msg.message_id

            except TelegramRetryAfter as e:
                print(f"[Telegram FloodWait] Sleeping for {e.retry_after}s...")
                await asyncio.sleep(e.retry_after)
            except TelegramAPIError as e:
                print(f"[Telegram API Error] {e}")
                return None
            except Exception as e:
                print(f"[Telegram Dispatch Exception] {e}")
                return None

        return None
