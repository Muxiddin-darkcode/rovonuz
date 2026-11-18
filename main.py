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


async def start_render_health_server():
    """Binds to Render's dynamic $PORT to pass Web Service health checks."""
    port_str = os.getenv("PORT")
    if not port_str:
        return
    try:
        from aiohttp import web
        app = web.Application()
        async def health(request):
            return web.Response(text="ROVON.UZ Newsroom Daemon Running OK", content_type="text/plain")
        app.router.add_get("/", health)
        app.router.add_get("/health", health)
        runner = web.AppRunner(app)
        await runner.setup()
        port = int(port_str)
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        print(f"[Render Server] Health check server listening on port {port}", flush=True)
    except Exception as e:
        print(f"[Render Server Warning] Could not start health server: {e}", flush=True)


async def run_newsroom_daemon():
    print("=" * 60)
    print("ROVON.UZ — 100% TELEGRAM AI MEDIA NEWSROOM")
    print("=" * 60, flush=True)

    # 0. Start Render HTTP Health Server if $PORT is provided
    await start_render_health_server()

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
