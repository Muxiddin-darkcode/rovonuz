"""
ROVON.UZ - Advanced AI Media Intelligence System
100% Telegram-Powered Newsroom Engine (No Web UI).

Components:
- Database Synchronizer (SQLite/PostgreSQL)
- Autonomous Auto-Pilot Worker (Continuous Telegram Harvester)
- Interactive 4-AI Dispatcher & Editorial Copilot Bot (@rovonuz_bot)
- Telegram Target Channel Dispatcher (@rovonuz)
"""

import os
import asyncio
from app.core.config import settings
from app.db.session import engine, Base
import app.db.models
from app.workers.autopilot_worker import autopilot_service
from app.telegram_gateway.bot_service import dp, bot, setup_bot_commands


async def run_newsroom_daemon():
    print("=" * 60)
    print("ROVON.UZ — 100% TELEGRAM AI MEDIA NEWSROOM")
    print("=" * 60, flush=True)

    # 1. Initialize Storage & Database
    os.makedirs("storage/cards", exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("[Database] Schema synchronized successfully.", flush=True)

    # 2. Launch Auto-Pilot Background Channel Harvester
    autopilot_service.start()
    print("[AutoPilot] Background channel harvester started (Monitoring official channels).", flush=True)

    # 3. Setup Telegram Bot Commands & Start Polling
    print("[Telegram Bot] Registering native bot menu commands...", flush=True)
    await setup_bot_commands(bot)
    print(f"[Telegram Bot] Running @rovonuz_bot -> {settings.TELEGRAM_CHANNEL_ID}. Streamlined cockpit active.", flush=True)

    # Resilient Polling Loop with auto-reconnect
    while True:
        try:
            await dp.start_polling(
                bot,
                allowed_updates=dp.resolve_used_update_types(),
                drop_pending_updates=True
            )
            break
        except asyncio.CancelledError:
            print("[Telegram Bot] Polling cancelled gracefully.", flush=True)
            break
        except Exception as e:
            print(f"[Bot Error] {e}. Reconnecting in 5s...", flush=True)
            await asyncio.sleep(5)


if __name__ == "__main__":
    try:
        asyncio.run(run_newsroom_daemon())
    except (KeyboardInterrupt, SystemExit):
        print("[Server] Newsroom stopped gracefully.", flush=True)
