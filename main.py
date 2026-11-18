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
    """
    Binds to Render's dynamic $PORT to pass Web Service health checks
    and provide 100% 24/7 uptime for UptimeRobot, Cron-Job, and Ping monitors.
    Supports GET, HEAD, POST, OPTIONS across /, /health, /ping, /status, /uptime.
    """
    port_str = os.getenv("PORT") or os.getenv("SERVER_PORT") or "10000"
    try:
        from aiohttp import web
        app = web.Application()

        async def health_handler(request: web.Request):
            accept = request.headers.get("Accept", "")
            # If opened in a web browser, show a branded ROVON.UZ status card
            if "text/html" in accept and request.path == "/":
                html_content = """<!DOCTYPE html>
<html lang="uz">
<head>
    <meta charset="UTF-8">
    <title>ROVON.UZ | AI Newsroom Live</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #04142A; color: #fff; display: flex; align-items: center; justify-content: center; height: 100vh; margin: 0; }
        .card { background: #0A2244; padding: 40px; border-radius: 18px; border: 1px solid #1E4173; text-align: center; max-width: 480px; width: 90%; box-shadow: 0 10px 40px rgba(0,0,0,0.6); }
        .badge { background: #10B981; color: #fff; padding: 6px 16px; border-radius: 20px; font-weight: bold; font-size: 14px; display: inline-block; margin-bottom: 20px; }
        h1 { margin: 0 0 10px 0; font-size: 32px; letter-spacing: 1px; }
        p { color: #94A3B8; line-height: 1.6; margin: 8px 0; }
        .channel-btn { display: inline-block; margin-top: 15px; background: #E61E2B; color: #fff; padding: 10px 24px; border-radius: 8px; text-decoration: none; font-weight: bold; }
        .footer { margin-top: 25px; border-top: 1px solid #1E4173; padding-top: 15px; font-size: 13px; color: #64748B; }
    </style>
</head>
<body>
    <div class="card">
        <span class="badge">● 24/7 ONLINE</span>
        <h1>ROVON<span style="color: #E61E2B;">.UZ</span></h1>
        <p><b>4-AI Media Intelligence & Autonomous Newsroom</b></p>
        <p>Render Server & UptimeRobot Monitor: <b>Active</b></p>
        <a href="https://t.me/rovonuz" class="channel-btn">Telegram: @rovonuz</a>
        <div class="footer">Voqealar ravon, axborot aniq.</div>
    </div>
</body>
</html>"""
                return web.Response(text=html_content, content_type="text/html", status=200)

            # JSON response for UptimeRobot, Head checks, and API monitors
            return web.json_response({
                "status": "ONLINE",
                "service": "ROVON.UZ 4-AI Autonomous Newsroom",
                "uptime_robot": "AWAKE",
                "render_health": "OK",
                "channel": settings.TELEGRAM_CHANNEL_ID,
                "bot": "@rovonuz_bot"
            }, status=200, headers={
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "no-cache",
            })

        # Register all ping paths and HTTP methods (GET, HEAD, POST, OPTIONS)
        for path in ["/", "/health", "/ping", "/status", "/uptime"]:
            app.router.add_route("*", path, health_handler)

        runner = web.AppRunner(app)
        await runner.setup()
        port = int(port_str)
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        print(f"[Render Server] Live 24/7 Health Server listening on 0.0.0.0:{port} (Accepts GET/HEAD for UptimeRobot).", flush=True)
    except Exception as e:
        print(f"[Render Server Warning] Could not start health server: {e}", flush=True)


async def run_keepalive_pinger():
    """
    Self-ping keep-alive loop: Automatically pings Render's public URL every 7 minutes.
    Render free tier puts inactive apps to sleep after 15 minutes.
    This internal loop guarantees Render NEVER sleeps even if UptimeRobot pauses!
    """
    await asyncio.sleep(45)  # Wait for daemon and HTTP server to spin up
    url = os.getenv("RENDER_EXTERNAL_URL") or os.getenv("UPTIME_URL")
    if not url:
        print("[KeepAlive] RENDER_EXTERNAL_URL not set in environment. Relying on external UptimeRobot.", flush=True)
        return

    import httpx
    clean_url = f"{url.rstrip('/')}/health"
    print(f"[KeepAlive] Automatic self-pinger active for: {clean_url} (Every 7 minutes).", flush=True)
    while True:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                res = await client.get(clean_url)
                print(f"[KeepAlive Self-Ping] Status {res.status_code} OK -> Render sleep timer reset.", flush=True)
        except Exception as e:
            print(f"[KeepAlive Self-Ping Warning] {e}", flush=True)

        await asyncio.sleep(420)  # 7 minutes (420s) - Render sleeps after 15 minutes


async def run_newsroom_daemon():
    print("=" * 60)
    print("ROVON.UZ — 100% TELEGRAM AI MEDIA NEWSROOM")
    print("=" * 60, flush=True)

    # 0. Start Render HTTP Health Server & Background Keep-Alive Self-Pinger
    await start_render_health_server()
    asyncio.create_task(run_keepalive_pinger())

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
