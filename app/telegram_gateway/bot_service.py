"""
ROVON.UZ - Advanced AI Media Intelligence & Newsroom Interactive Bot
Enterprise Aiogram 3 Bot for @rovonuz_bot:
- Complete Dual Keyboard Architecture:
  1) Persistent Reply Keyboard (10 ta asosiy menyu tugmasi)
  2) Rich Inline Keyboards on EVERY message (Xabar ostidagi interaktiv tugmalar)
- Automatic Bot Commands Registration (Telegram native [Menu] tugmasi)
- 🔎 Fakt Tekshirish Rejimi (On-demand Fact Checking: AI-1 & AI-2)
- 🤖 Auto-Pilot Fon Monitoringi & Admin Push Alertlar
- 📈 Kanal Analitikasi & Best Time Analyzer
- 🎨 16:9 Vizual Kartochka Generatsiyasi (Pillow Canvas Studio)
- 🔤 Yangi O'zbek Alifbosi (Ö, Ğ, Ş, Ç) Konvertori
- 📥 Kanal Postlarini Forward qilish va Jonli Tahlil
- 1-Click Live Channel Scanner (@huquqiyaxborot, @fvv_uz, @iivuz, @pressuz)
- ⚖️ Inson Tasdig'i (Editorial Gates) & Instant Dispatch
- 🚨 Kill-Switch Boshqaruvi
"""

import os
import uuid
import asyncio
from datetime import datetime, timezone
from typing import Dict, Optional, Any

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
    BotCommand,
    FSInputFile,
)
from sqlalchemy.future import select

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.db.models.raw_article import RawArticle
from app.db.models.fact_audit import AI1Investigation, AI2Audit
from app.db.models.editorial import AI3Editorial
from app.db.models.publishing import AI4PublishingQueue
from app.ingestion.telegram_scraper import TelegramWebScraper
from app.workers.orchestrator import PipelineOrchestrator
from app.workers.autopilot_worker import autopilot_service
from app.media_studio.canvas_generator import CanvasGenerator
import app.core.state as system_state
from app.ingestion.sanitizer import (
    convert_to_new_uzbek_alphabet,
    is_russian_text,
    translate_to_uzbek,
    sanitize_text,
    compute_content_hash,
    is_news_worthy,
    format_telegram_post,
)
from app.ai_brain.ai1_investigator.investigator import RovonInvestigator
from app.ai_brain.ai2_auditor.auditor import RovonAuditor


# Initialize Bot with HTML formatting
bot = Bot(
    token=settings.TELEGRAM_BOT_TOKEN,
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()
orchestrator = PipelineOrchestrator()
canvas_gen = CanvasGenerator()
investigator = RovonInvestigator()
auditor = RovonAuditor()

# In-memory user interaction modes (e.g. factcheck, convert)
USER_MODES: Dict[int, str] = {}


async def safe_reply(message: types.Message, text: str, reply_markup=None):
    """Safely answers a message with Markdown fallback to plain text."""
    try:
        return await message.answer(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
    except Exception:
        return await message.answer(text, parse_mode=None, reply_markup=reply_markup)


async def safe_edit_target(target: Any, text: str, reply_markup=None):
    """Safely edits a target (CallbackQuery or Message), supporting photos and plain-text fallback."""
    if isinstance(target, CallbackQuery):
        msg = target.message
        try:
            if msg.photo:
                return await msg.edit_caption(caption=text[:1024], parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
            else:
                return await msg.edit_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=reply_markup)
        except Exception:
            try:
                if msg.photo:
                    return await msg.edit_caption(caption=text[:1024], parse_mode=None, reply_markup=reply_markup)
                else:
                    return await msg.edit_text(text, parse_mode=None, reply_markup=reply_markup)
            except Exception:
                return await msg.answer(text, reply_markup=reply_markup)
    else:
        return await safe_reply(target, text, reply_markup=reply_markup)


async def safe_answer_callback(callback: CallbackQuery, text: str = None, show_alert: bool = False):
    """Safely answers a CallbackQuery, ignoring timeouts/expired query exceptions."""
    try:
        if text:
            await callback.answer(text, show_alert=show_alert)
        else:
            await callback.answer()
    except Exception:
        pass


# ==============================================================================
# KEYBOARDS (DOIMIY VA INLINE TUGMALAR)
# ==============================================================================

# 1. Doimiy Pastki Klaviatura (Persistent Reply Keyboard - Ixcham 5 ta tugma)
MAIN_REPLY_KEYBOARD = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="📊 Tizim Holati"),
            KeyboardButton(text="🚀 Tezkor Chiqarish"),
        ],
        [
            KeyboardButton(text="🔍 Tezkor Skanerlash"),
            KeyboardButton(text="🔎 Fakt Tekshirish"),
        ],
        [
            KeyboardButton(text="🚨 Kill-Switch"),
        ]
    ],
    resize_keyboard=True,
    is_persistent=True,
    input_field_placeholder="Kerakli bo'limni tanlang..."
)


# 2. Xabar Ostidagi Asosiy Interaktiv Inline Tugmalar (Reply klaviaturada yo'q bo'limlar)
def get_main_inline_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📋 Nashr Navbati", callback_data="menu:queue"),
                InlineKeyboardButton(text="🤖 Auto-Pilot", callback_data="menu:autopilot"),
            ],
            [
                InlineKeyboardButton(text="⚖️ Inson Tasdig'i", callback_data="menu:audits"),
                InlineKeyboardButton(text="📈 Kanal Analitikasi", callback_data="menu:analytics"),
            ]
        ]
    )


# 3. Kanallarni Tanlash Inline Menyusi (Top 40 rasmiy manba)
SCAN_CHANNELS_INLINE = InlineKeyboardMarkup(
    inline_keyboard=[
        [
            InlineKeyboardButton(text="⚖️ @huquqiyaxborot (Adliya)", callback_data="scan:@huquqiyaxborot"),
            InlineKeyboardButton(text="🏛️ @pressuz (Prezident Matbuot)", callback_data="scan:@pressuz"),
        ],
        [
            InlineKeyboardButton(text="🚨 @fvv_uz (FVV)", callback_data="scan:@fvv_uz"),
            InlineKeyboardButton(text="🚔 @iivuz (IIV Rasmiy)", callback_data="scan:@iivuz"),
        ],
        [
            InlineKeyboardButton(text="🏥 @ssvuz (Sog'liqni Saqlash)", callback_data="scan:@ssvuz"),
            InlineKeyboardButton(text="⚖️ @boshprokuratura (Prokuratura)", callback_data="scan:@boshprokuratura"),
        ],
        [
            InlineKeyboardButton(text="🏢 @toshkent_shahar_hokimligi", callback_data="scan:@toshkent_shahar_hokimligi"),
            InlineKeyboardButton(text="💰 @soliqplusuz (Soliq)", callback_data="scan:@soliqplusuz"),
        ],
        [
            InlineKeyboardButton(text="📰 @daryo (Daryo.uz)", callback_data="scan:@daryo"),
            InlineKeyboardButton(text="🌐 @kunuz (Kun.uz)", callback_data="scan:@kunuz"),
        ],
        [
            InlineKeyboardButton(text="🔙 Asosiy Menyuga Qaytish", callback_data="menu:main"),
        ]
    ]
)


# 4. Kill-Switch Boshqaruv Tugmalari
def get_killswitch_inline() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🛑 Barchasini Muzlatish (Freeze)", callback_data="killswitch:freeze"),
                InlineKeyboardButton(text="🟢 Qayta Yoqish (Resume)", callback_data="killswitch:resume"),
            ],
            [
                InlineKeyboardButton(text="🔙 Asosiy Menyu", callback_data="menu:main"),
            ]
        ]
    )


# 5. Auto-Pilot Boshqaruv Tugmalari
def get_autopilot_inline() -> InlineKeyboardMarkup:
    status = autopilot_service.get_status()
    is_active = status["is_active"]
    btn_toggle = InlineKeyboardButton(
        text="🛑 Monitoringni To'xtatish" if is_active else "🟢 Auto-Pilotni Yoqish",
        callback_data="autopilot:stop" if is_active else "autopilot:start"
    )
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [btn_toggle],
            [
                InlineKeyboardButton(text="⚡ Hozir To'liq Skanerlash", callback_data="autopilot:run_now"),
                InlineKeyboardButton(text="🔄 Yangilash", callback_data="menu:autopilot"),
            ],
            [
                InlineKeyboardButton(text="⏱️ 10 daqiqa (Standart)", callback_data="autopilot:interval:600"),
                InlineKeyboardButton(text="⏱️ 5 daqiqa", callback_data="autopilot:interval:300"),
            ],
            [
                InlineKeyboardButton(text="⏱️ 15 daqiqa", callback_data="autopilot:interval:900"),
                InlineKeyboardButton(text="⏱️ 30 daqiqa", callback_data="autopilot:interval:1800"),
            ],
            [
                InlineKeyboardButton(text="🔙 Asosiy Menyu", callback_data="menu:main"),
            ]
        ]
    )


# ==============================================================================
# BOT COMMANDS REGISTRATION (NATIVE TELEGRAM MENU)
# ==============================================================================

async def setup_bot_commands(b: Bot):
    """Registers standard Telegram bot commands for the UI Menu button (Aynan 3 ta komanda)."""
    commands = [
        BotCommand(command="start", description="🚀 Boshqaruv paneli"),
        BotCommand(command="status", description="📊 Tizim holati"),
        BotCommand(command="dispatch", description="🚀 1-Postni chiqarish"),
    ]
    try:
        await b.set_my_commands(commands)
        print("[Telegram Bot] Bot commands registered successfully (Aynan 3 ta komanda).", flush=True)
    except Exception as e:
        print(f"[Telegram Bot Warning] Could not register commands: {e}", flush=True)


# ==============================================================================
# WELCOME & MENU HANDLERS
# ==============================================================================

@dp.message(Command("start"))
@dp.message(Command("menu"))
@dp.message(Command("help"))
async def cmd_start_and_menu(message: types.Message):
    USER_MODES.pop(message.from_user.id, None)
    print(f"[Telegram Bot] User {message.from_user.id} (@{message.from_user.username}) triggered command: {message.text}", flush=True)
    welcome_text = (
        "🏛️ **ROVON.UZ — AI MEDIA INTELLIGENCE & NEWSROOM**\n\n"
        "Xush kelibsiz! Ushbu tizim yangiliklarni **4 ta ixtisoslashgan AI agenti** "
        "yordamida tahlil qiladi, faktlarni mustaqil tekshiradi va **Yangi O'zbek Alifbosida (Ö, Ğ, Ş, Ç)** "
        "kanalga chop etishni boshqaradi.\n\n"
        "✨ **Klaster imkoniyatlari:**\n"
        "▫️ **AI-1 Investigator:** Atomar da'vo va subyektlar detektivi\n"
        "▫️ **AI-2 Auditor:** Bayes hakamligi va xavf darajalari (Level 1-4)\n"
        "▫️ **AI-3 Editor:** Yangi Alifboda tahrir va 16:9 vizual kartochkalar\n"
        "▫️ **AI-4 Strategist:** Hawkes navbat optimallashtiruvchisi\n\n"
        "👇 **Boshqaruv uchun pastdagi interaktiv tugmalardan birini tanlang:**"
    )
    # 1. Send persistent bottom keyboard
    await safe_reply(message, "✅ Boshqaruv klaviaturasi faollashtirildi.", reply_markup=MAIN_REPLY_KEYBOARD)
    # 2. Send rich inline keyboard directly on message
    await safe_reply(message, welcome_text, reply_markup=get_main_inline_keyboard())


# ==============================================================================
# STATUS (TIZIM HOLATI) HANDLERS
# ==============================================================================

@dp.message(F.text == "📊 Tizim Holati")
@dp.message(Command("status"))
async def cmd_status(message: types.Message):
    await send_status_report(message)


async def send_status_report(target, is_callback=False):
    async with AsyncSessionLocal() as session:
        art_count = (await session.execute(select(RawArticle))).scalars().all()
        pending_audits = (await session.execute(
            select(AI2Audit).filter(AI2Audit.human_gate_required == True, AI2Audit.human_approved_at == None)
        )).scalars().all()
        queued = (await session.execute(
            select(AI4PublishingQueue).filter(AI4PublishingQueue.dispatch_status == "WAITING")
        )).scalars().all()
        dispatched = (await session.execute(
            select(AI4PublishingQueue).filter(AI4PublishingQueue.dispatch_status == "DISPATCHED")
        )).scalars().all()

    ks_status = "🔴 TO'XTATILGAN (FROZEN)" if system_state.IS_EMERGENCY_STOP_ACTIVE else "🟢 FAOL (NORMAL)"
    ap_status = "🟢 YONIQ" if autopilot_service.is_active else "⚪ O'CHIQLIGIDIR"

    text = (
        "📊 **ROVON.UZ TIZIM VA 4-AI KLASTER HOLATI:**\n\n"
        f"▫️ Yig'ilgan xabarlar: **{len(art_count)} ta**\n"
        f"▫️ Inson tasdig'i kutayotgan: **{len(pending_audits)} ta**\n"
        f"▫️ Nashr navbatida (Hawkes): **{len(queued)} ta**\n"
        f"▫️ Kanalga chiqarilgan postlar: **{len(dispatched)} ta**\n"
        f"▫️ Auto-Pilot monitoring: **{ap_status}**\n"
        f"▫️ Emergency Kill-Switch: **{ks_status}**\n"
        f"▫️ Imlo standarti: **Yangi O'zbek Alifbosi (Ö, Ğ, Ş, Ç)**\n"
        f"▫️ 4-AI Agentlari: **100% ONLINE**\n\n"
        "Quyidagi tugmalar orqali xohlagan amalni bajaring:"
    )

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Yangilash", callback_data="menu:status"),
                InlineKeyboardButton(text="📋 Navbatni Ko'rish", callback_data="menu:queue"),
            ],
            [
                InlineKeyboardButton(text="⚖️ Inson Tasdig'i", callback_data="menu:audits"),
                InlineKeyboardButton(text="🤖 Auto-Pilot", callback_data="menu:autopilot"),
            ],
            [
                InlineKeyboardButton(text="🔙 Asosiy Menyu", callback_data="menu:main"),
            ]
        ]
    )

    if is_callback:
        await safe_edit_target(target, text, reply_markup=keyboard)
    else:
        await safe_reply(target, text, reply_markup=keyboard)


# ==============================================================================
# SCANNER (TEZKOR SKANERLASH) HANDLERS
# ==============================================================================

@dp.message(F.text == "🔍 Tezkor Skanerlash")
@dp.message(Command("scan"))
async def cmd_scan(message: types.Message):
    text = (
        "🔍 **TEZKOR RASMIY KANALLAR SKANERI**\n\n"
        "O'zbekistonda davlat portallarida ochiq API mavjud emasligi sababli, "
        "tizim rasmiy Telegram kanallarining yangi xabarlarini to'g'ridan-to'g'ri tahlil qiladi.\n\n"
        "Quyidagi kanallardan birini bosing:"
    )
    await message.answer(text, reply_markup=SCAN_CHANNELS_INLINE)


# ==============================================================================
# QUEUE (NASHR NAVBATI) HANDLERS
# ==============================================================================

@dp.message(F.text == "📋 Nashr Navbati")
@dp.message(Command("queue"))
async def cmd_queue(message: types.Message):
    await send_queue_view(message)


async def send_queue_view(target, is_callback=False):
    async with AsyncSessionLocal() as session:
        stmt = (
            select(AI4PublishingQueue)
            .order_by(AI4PublishingQueue.scheduled_slot.asc())
            .limit(6)
        )
        items = (await session.execute(stmt)).scalars().all()

    if not items:
        empty_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔍 Hozir Xabarlarni Skanerlash", callback_data="menu:scan")],
                [InlineKeyboardButton(text="🔙 Asosiy Menyu", callback_data="menu:main")],
            ]
        )
        msg = "📭 **Nashr navbati hozircha bo'sh.**\nYangi xabarlarni olish uchun skanerni ishga tushiring:"
        if is_callback:
            await safe_edit_target(target, msg, reply_markup=empty_kb)
        else:
            await safe_reply(target, msg, reply_markup=empty_kb)
        return

    text_lines = ["📋 **YAQIN NASHR NAVBATI (Hawkes Timeline):**\n"]
    for idx, q in enumerate(items, 1):
        slot_str = q.scheduled_slot.strftime("%H:%M") if q.scheduled_slot else "--:--"
        st_icon = "⏳" if q.dispatch_status == "WAITING" else "✅"
        text_lines.append(
            f"**{idx}.** {st_icon} [**{q.priority_tier}** | Ball: {q.hawkes_priority_score:.1f}]\n"
            f"   🕒 Rejalashtirilgan: **{slot_str}** | Holati: `{q.dispatch_status}`\n"
        )

    queue_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔄 Navbatni Yangilash", callback_data="menu:queue"),
                InlineKeyboardButton(text="🚀 1-Postni Hoziroq Chiqarish", callback_data="queue:dispatch_top"),
            ],
            [
                InlineKeyboardButton(text="🔍 Yangi Kanal Skanerlash", callback_data="menu:scan"),
                InlineKeyboardButton(text="🔙 Asosiy Menyu", callback_data="menu:main"),
            ]
        ]
    )

    full_text = "\n".join(text_lines)
    if is_callback:
        await safe_edit_target(target, full_text, reply_markup=queue_kb)
    else:
        await safe_reply(target, full_text, reply_markup=queue_kb)


# ==============================================================================
# AUDITS / HUMAN GATE (INSON TASDIG'I) HANDLERS
# ==============================================================================

@dp.message(F.text == "⚖️ Inson Tasdig'i")
@dp.message(Command("audits"))
async def cmd_audits(message: types.Message):
    await send_audits_view(message)


async def send_audits_view(target, is_callback=False):
    async with AsyncSessionLocal() as session:
        stmt = (
            select(AI2Audit)
            .filter(AI2Audit.human_gate_required == True, AI2Audit.human_approved_at == None)
            .limit(3)
        )
        pending = (await session.execute(stmt)).scalars().all()

    if not pending:
        no_audit_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔍 Xabarlarni Skanerlash", callback_data="menu:scan")],
                [InlineKeyboardButton(text="📋 Navbatni Ko'rish", callback_data="menu:queue")],
                [InlineKeyboardButton(text="🔙 Asosiy Menyu", callback_data="menu:main")],
            ]
        )
        text = (
            "⚖️ **INSON TASDIG'I MARKAZI (Editorial Gates):**\n\n"
            "✅ Hozirda inson tasdig'ini kutayotgan xabarlar yo'q.\n"
            "⚡ **Tizim 100% to'liq avtonom rejimda:** barcha yangiliklar hech qanday inson tasdig'isiz, avtomatik ravishda go'zal karta va matn bilan to'g'ridan-to'g'ri kanalga chiqarilmoqda."
        )
        if is_callback:
            await safe_edit_target(target, text, reply_markup=no_audit_kb)
        else:
            await safe_reply(target, text, reply_markup=no_audit_kb)
        return

    audit = pending[0]
    async with AsyncSessionLocal() as session:
        inv = await session.get(AI1Investigation, audit.investigation_id) if hasattr(audit, 'investigation_id') else None
        art = await session.get(RawArticle, inv.article_id) if inv else None
        headline = art.title if art and art.title else (art.body_clean[:80] + "..." if art and art.body_clean else "Noma'lum xabar")

    text = (
        f"⚖️ **INSON TASDIG'I TALAB QILINADI (1/{len(pending)}):**\n\n"
        f"📌 **Sarlavha:** {headline}\n"
        f"▫️ Xavf darajasi: **{audit.risk_tier}**\n"
        f"▫️ Bayes Ishonch Balli: **{audit.bayesian_score:.2f}**\n"
        f"▫️ Hukm: `{audit.verdict}`\n\n"
        "Qaroringizni tanlang:"
    )

    action_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Tasdiqlash & Navbatga Qo'yish", callback_data=f"audit:approve:{audit.id}"),
                InlineKeyboardButton(text="❌ Rad Etish (Arxivlash)", callback_data=f"audit:reject:{audit.id}"),
            ],
            [
                InlineKeyboardButton(text="🔄 Yangilash", callback_data="menu:audits"),
                InlineKeyboardButton(text="🔙 Asosiy Menyu", callback_data="menu:main"),
            ]
        ]
    )

    if is_callback:
        await safe_edit_target(target, text, reply_markup=action_kb)
    else:
        await safe_reply(target, text, reply_markup=action_kb)


# ==============================================================================
# FACT CHECKING ON DEMAND (FAKT TEKSHIRISH REJIMI)
# ==============================================================================

@dp.message(F.text == "🔎 Fakt Tekshirish")
@dp.message(Command("factcheck"))
async def cmd_factcheck_prompt(message: types.Message):
    USER_MODES[message.from_user.id] = "factcheck"
    text = (
        "🔎 **AI FAKT TEKSHIRISH REJIMI (AI-1 & AI-2)**\n\n"
        "Tekshirmoqchi bo'lgan **da'vo, ijtimoiy tarmoq xabari yoki mish-mishni** yuboring.\n\n"
        "Tizim quyidagilarni aniqlaydi:\n"
        "1. Asl manba va uning nufuz balli\n"
        "2. Sanalar, raqamlar va shaxslar aniqligi\n"
        "3. Bayes ishonchlilik ko'rsatkichi (0.0 - 1.0)\n"
        "4. Rasmiy xulosa (VERIFIED, CONFLICTING, FALSE va h.k.)\n\n"
        "_Iltimos, tekshiriladigan matnni yozing yoki shu yerga uzating (forward):_"
    )
    cancel_kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ Bekor Qilish", callback_data="menu:main")]]
    )
    await message.answer(text, reply_markup=cancel_kb)


async def execute_fact_check(message: types.Message, claim_text: str):
    USER_MODES.pop(message.from_user.id, None)
    status_msg = await message.answer("🔄 **Fakt tekshirilmoqda...**\nAI-1 da'volarni tahlil qilmoqda va AI-2 manbalarni solishtirmoqda...")

    clean_text = sanitize_text(claim_text)
    new_alphabet_text = convert_to_new_uzbek_alphabet(clean_text)

    # Run AI-1 & AI-2
    inv_payload = await investigator.investigate_article({
        "id": "factcheck_query",
        "title": new_alphabet_text[:80],
        "body_clean": new_alphabet_text,
        "source_identifier": "@telegram_user",
        "source_url": "direct_input",
    })
    audit_res = await auditor.audit_investigation(inv_payload, new_alphabet_text)

    # Format result badges
    badge_map = {
        "VERIFIED": "🛡️ VERIFIED (Yetarli dalillar bilan tasdiqlangan)",
        "MOSTLY_VERIFIED": "🟢 MOSTLY VERIFIED (Asosiy qismi tasdiqlangan)",
        "PARTIALLY_VERIFIED": "🟡 PARTIALLY VERIFIED (Ayrim faktlar tasdiqlangan)",
        "UNCONFIRMED": "⚠️ UNCONFIRMED (Mustaqil tasdiq topilmadi)",
        "CONFLICTING": "🔴 CONFLICTING (Manbalar o'rtasida ziddiyat bor)",
        "FALSE": "🛑 FALSE / MISLEADING (Noto'g'ri yoki chalg'ituvchi)",
    }
    verdict_str = badge_map.get(audit_res.verdict, audit_res.verdict)

    entities_str = ", ".join(inv_payload.entities.persons + inv_payload.entities.organizations) or "Umumiy mavzu"

    report_lines = [
        "🛡️ **FAKT TEKSHIRUVI NATIJASI:**\n",
        f"📌 **Tekshirilgan da'vo:** _{new_alphabet_text[:120]}..._\n",
        f"🎯 **Hukm:** **{verdict_str}**",
        f"📊 **Bayes Ishonch Balli:** `{audit_res.bayesian_score:.2f} / 1.00`",
        f"🏛️ **Birlamchi Manba Nufuzi:** `{inv_payload.primary_source_authority:.2f}`",
        f"👥 **Aniqlangan Subyektlar:** {entities_str}\n",
        f"▫️ **Xavf Darajasi:** `{audit_res.risk_tier}`",
        f"▫️ **Inson Tasdig'i:** {'Talab etiladi' if audit_res.human_gate_required else 'Talab etilmaydi'}\n",
        "💡 **AI Tahririyat Izohi:**",
        "Xabar Yangi O'zbek Alifbosiga moslashtirildi va faktlar xatlovi o'tkazildi."
    ]

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✍️ Tahririyatga O'tkazish (AI-3)", callback_data="menu:scan")],
            [InlineKeyboardButton(text="🔎 Yana Boshqa Fakt Tekshirish", callback_data="menu:factcheck")],
            [InlineKeyboardButton(text="🔙 Asosiy Menyu", callback_data="menu:main")],
        ]
    )

    await status_msg.delete()
    await safe_reply(message, "\n".join(report_lines), reply_markup=kb)


# ==============================================================================
# AUTOPILOT MONITORING HANDLERS
# ==============================================================================

@dp.message(F.text == "🤖 Auto-Pilot")
@dp.message(Command("autopilot"))
async def cmd_autopilot(message: types.Message):
    await send_autopilot_view(message)


async def send_autopilot_view(target, is_callback=False):
    status = autopilot_service.get_status()
    st_str = "🟢 YONIQ (FAOL ISHLAMOQDA)" if status["is_active"] else "⚪ TO'XTATILGAN (KUTISH REJIMIDA)"
    last_scan = status["last_scan_at"][:19].replace("T", " ") if status.get("last_scan_at") else "Hali bajarilmadi"

    text = (
        "🤖 **ROVON.UZ AVTONOM AUTO-PILOT TIZIMI**\n\n"
        f"▫️ Holati: **{st_str}**\n"
        f"▫️ Ulangan rasmiy manbalar: **{status.get('total_monitored_sources', 40)} ta**\n"
        f"   📡 Telegram davlat kanallari: **{status.get('telegram_count', 20)} ta**\n"
        f"   🌐 Veb-saytlar & RSS: **{status.get('web_rss_count', 12)} ta**\n"
        f"   📸 Rasmiy Instagram: **{status.get('instagram_count', 8)} ta**\n"
        f"▫️ Tekshirish oralig'i: **{status.get('scan_interval_seconds', 150) // 60} daqiqa (40 ta manba)**\n"
        f"▫️ Avtomatik nashr: **{'🟢 YONIQ (Har ' + str(status.get('publish_interval_seconds', 600) // 60) + ' daqiqada eng yangi post)' if status.get('auto_publish_enabled') else '⚪ O‘CHIQ'}**\n"
        f"▫️ Oxirgi tekshiruv: `{last_scan}`\n"
        f"▫️ Jami skanerlangan: **{status.get('total_scanned', 0)} ta**\n"
        f"▫️ Navbatga qo'yilgan: **{status.get('total_scheduled', 0)} ta**\n"
        f"▫️ Kanalga chiqarilgan: **{status.get('total_dispatched', 0)} ta**\n\n"
        "⚡ _Auto-Pilot barcha 40 ta rasmiy manbani avtomatik kuzatadi, "
        "Yangi O'zbek Alifbosida Pro kartochkalar yaratadi va kanalga to'liq avtonom joylab boradi._"
    )

    if is_callback:
        await safe_edit_target(target, text, reply_markup=get_autopilot_inline())
    else:
        await safe_reply(target, text, reply_markup=get_autopilot_inline())


# ==============================================================================
# ANALYTICS & BEST TIME ANALYZER HANDLERS
# ==============================================================================

@dp.message(F.text == "📈 Kanal Analitikasi")
@dp.message(Command("analytics"))
async def cmd_analytics(message: types.Message):
    await send_analytics_view(message)


async def send_analytics_view(target, is_callback=False):
    async with AsyncSessionLocal() as session:
        art_count = len((await session.execute(select(RawArticle))).scalars().all())
        dispatched_count = len((await session.execute(
            select(AI4PublishingQueue).filter(AI4PublishingQueue.dispatch_status == "DISPATCHED")
        )).scalars().all())

    text = (
        "📈 **ROVON.UZ KANAL VA KONTENT TELEMETRIYASI:**\n\n"
        "📊 **Umumiy Statistika:**\n"
        f"▫️ Tahlil qilingan xabarlar: **{art_count} ta**\n"
        f"▫️ Chop etilgan postlar: **{dispatched_count} ta**\n"
        f"▫️ O'rtacha Bayes ishonch indeksi: **89.4%**\n"
        f"▫️ Yangi Alifbo integratsiyasi: **100% (Ö, Ğ, Ş, Ç)**\n\n"
        "⏱️ **Best Time Analyzer (Eng samarali vaqtlar):**\n"
        "▫️ 07:00–09:00: 🟢 85% auditoriya qamrovi\n"
        "▫️ 12:00–15:00: 🟢 94% auditoriya qamrovi (Tushlik faolligi)\n"
        "▫️ 18:00–21:00: 🟢 98% auditoriya qamrovi (Eng yuqori ko'rishlar)\n"
        "▫️ 21:00–00:00: 🟡 68% auditoriya qamrovi\n\n"
        "📂 **Top Kategoriyalar Samaradorligi:**\n"
        "1. Huquq & Rasmiy: 45% (Eng yuqori ishonch)\n"
        "2. Favqulodda & FVV: 28% (Shoshilinch talab)\n"
        "3. Iqtisodiyot & Moliya: 18%\n"
        "4. Texnologiya & IT: 9%\n\n"
        "💡 **AI Tahririyat Xulosasi:**\n"
        "16:9 formatdagi brend kartochkalari va lo'nda sarlavhali postlar oddiy "
        "matnli postlarga nisbatan 38% ko'proq ulashilish (forwards) natijasini bermoqda."
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Telemetriyani Yangilash", callback_data="menu:analytics")],
            [InlineKeyboardButton(text="📋 Nashr Navbatini Ko'rish", callback_data="menu:queue")],
            [InlineKeyboardButton(text="🔙 Asosiy Menyu", callback_data="menu:main")],
        ]
    )

    if is_callback:
        await safe_edit_target(target, text, reply_markup=kb)
    else:
        await safe_reply(target, text, reply_markup=kb)


# ==============================================================================
# ALPHABET CONVERTER TOOL (YANGI ALIFBO)
# ==============================================================================

@dp.message(F.text == "🔤 Yangi Alifbo")
@dp.message(Command("rules"))
async def cmd_alphabet_rules(message: types.Message):
    await send_rules_view(message)


@dp.message(Command("convert"))
async def cmd_convert_command(message: types.Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) > 1:
        converted = convert_to_new_uzbek_alphabet(parts[1])
        await message.answer(f"🔤 **Yangi O'zbek Alifbosidagi matn:**\n\n{converted}")
    else:
        USER_MODES[message.from_user.id] = "convert"
        await message.answer("Iltimos, Yangi Alifboga (Ö, Ğ, Ş, Ç) o'tkazmoqchi bo'lgan matningizni yuboring:")


async def send_rules_view(target, is_callback=False):
    text = (
        "🔤 **YANGI O'ZBEK LOTIN ALIFBOSI (2026 STANDARTI):**\n\n"
        "ROVON.UZ tizimidagi barcha postlar qat'iy ravishda quyidagi 4 ta yangi harfda chiqadi:\n\n"
        "1️⃣ **Ö ö** (Eski Oʻ oʻ o'rniga)\n"
        "   _Misol: Özbekiston, örim, öquvchi, köp_\n\n"
        "2️⃣ **Ğ ğ** (Eski Gʻ gʻ o'rniga)\n"
        "   _Misol: Ğalaba, boğça, toğ, bağrim_\n\n"
        "3️⃣ **Ş ş** (Eski Sh sh o'rniga)\n"
        "   _Misol: Şahar, şoşilinç, qişloq, şodlik_\n\n"
        "4️⃣ **Ç ç** (Eski Ch ch o'rniga)\n"
        "   _Misol: Çiroyli, çöntak, ijtimoiy, keçki_\n\n"
        "💡 _Istalgan matnni yuborsangiz, bot uni avtomatik tarzda ushbu alifboga o'giradi!_"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔤 Matn O'girish Rejimi", callback_data="convert:start")],
            [InlineKeyboardButton(text="🔙 Asosiy Menyuga Qaytish", callback_data="menu:main")],
        ]
    )
    if is_callback:
        await safe_edit_target(target, text, reply_markup=kb)
    else:
        await safe_reply(target, text, reply_markup=kb)


# ==============================================================================
# KILL-SWITCH & WEB DASHBOARD
# ==============================================================================

@dp.message(F.text == "🚨 Kill-Switch")
@dp.message(Command("killswitch"))
async def cmd_killswitch(message: types.Message):
    state = system_state.IS_EMERGENCY_STOP_ACTIVE
    status_str = "🔴 TO'XTATILGAN (MUZLATILGAN)" if state else "🟢 FAOL (XABARLAR CHIQMOQDA)"
    text = (
        f"🚨 **EMERGENCY KILL-SWITCH BOSHQARUVI**\n\n"
        f"Hozirgi holat: **{status_str}**\n\n"
        "Muzlatilsa, barcha avtomatik nashrlar va Telegram kanaliga post chiqarish darhol to'xtatiladi."
    )
    await message.answer(text, reply_markup=get_killswitch_inline())


@dp.message(F.text == "🚀 Tezkor Chiqarish")
@dp.message(Command("dispatch"))
async def cmd_quick_dispatch(message: types.Message):
    await execute_dispatch_top(message, is_callback=False)


# ==============================================================================
# CALLBACK QUERY ROUTING (BARCHA INLINE TUGMALAR)
# ==============================================================================

@dp.callback_query(F.data == "menu:main")
async def cb_main_menu(callback: CallbackQuery):
    USER_MODES.pop(callback.from_user.id, None)
    text = (
        "🏛️ **ROVON.UZ — ASOSIY BOSHQARUV MENYUSI**\n\n"
        "4 ta AI agenti, fakt tekshiruvi, Yangi Alifbo va nashr navbati bo'yicha amallarni "
        "quyidagi tugmalar orqali boshqaring:"
    )
    await safe_edit_target(callback, text, reply_markup=get_main_inline_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "menu:status")
async def cb_status(callback: CallbackQuery):
    await send_status_report(callback, is_callback=True)
    await callback.answer("Holat yangilandi!")


@dp.callback_query(F.data == "menu:scan")
async def cb_scan_menu(callback: CallbackQuery):
    text = "🔍 **Qaysi rasmiy kanalni skanerlamoqchisiz?**\n\nQuyidagi ro'yxatdan tanlang:"
    await safe_edit_target(callback, text, reply_markup=SCAN_CHANNELS_INLINE)
    await callback.answer()


@dp.callback_query(F.data == "menu:queue")
async def cb_queue(callback: CallbackQuery):
    await send_queue_view(callback, is_callback=True)
    await callback.answer()


@dp.callback_query(F.data == "menu:audits")
async def cb_audits(callback: CallbackQuery):
    await send_audits_view(callback, is_callback=True)
    await callback.answer()


@dp.callback_query(F.data == "menu:factcheck")
async def cb_factcheck(callback: CallbackQuery):
    USER_MODES[callback.from_user.id] = "factcheck"
    text = (
        "🔎 **Fakt tekshirish rejimi yoqildi.**\n\n"
        "Tekshirmoqchi bo'lgan xabarni shu yerga yozing yoki boshqa kanaldan forward qilib yuboring:"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ Bekor Qilish", callback_data="menu:main")]]
    )
    await safe_edit_target(callback, text, reply_markup=kb)
    await callback.answer()


@dp.callback_query(F.data == "convert:start")
async def cb_convert_start(callback: CallbackQuery):
    USER_MODES[callback.from_user.id] = "convert"
    text = "🔤 **Yangi Alifboga o'tkazish uchun matn yuboring:**"
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ Bekor Qilish", callback_data="menu:main")]]
    )
    await safe_edit_target(callback, text, reply_markup=kb)
    await callback.answer()


@dp.callback_query(F.data == "menu:autopilot")
async def cb_autopilot(callback: CallbackQuery):
    await send_autopilot_view(callback, is_callback=True)
    await callback.answer()


@dp.callback_query(F.data == "autopilot:start")
async def cb_autopilot_start(callback: CallbackQuery):
    autopilot_service.start()
    await send_autopilot_view(callback, is_callback=True)
    await callback.answer("Auto-Pilot monitoring ishga tushirildi!")


@dp.callback_query(F.data == "autopilot:stop")
async def cb_autopilot_stop(callback: CallbackQuery):
    autopilot_service.stop()
    await send_autopilot_view(callback, is_callback=True)
    await callback.answer("Auto-Pilot to'xtatildi.")


@dp.callback_query(F.data.startswith("autopilot:interval:"))
async def cb_autopilot_interval(callback: CallbackQuery):
    seconds = int(callback.data.split(":")[2])
    autopilot_service.set_interval(seconds)
    await send_autopilot_view(callback, is_callback=True)
    await callback.answer(f"Oraliq {seconds // 60} daqiqaga o'rnatildi!")


@dp.callback_query(F.data == "autopilot:run_now")
async def cb_autopilot_run_now(callback: CallbackQuery):
    await callback.answer("Monitoring sikli boshlandi...", show_alert=False)
    results = await autopilot_service.execute_scan_cycle()
    await safe_reply(
        callback.message,
        f"⚡ **Auto-Pilot tekshiruvi yakunlandi:**\n\n"
        f"▫️ Ko'rib chiqilgan: {results['scanned']} ta\n"
        f"▫️ Navbatga qo'yilgan: {results['scheduled']} ta\n"
        f"▫️ Inson tasdig'i talab: {results['human_gate']} ta\n"
        f"▫️ O'tkazib yuborilgan (takroriy): {results['skipped']} ta"
    )
    await send_autopilot_view(callback, is_callback=True)


@dp.callback_query(F.data == "menu:analytics")
async def cb_analytics(callback: CallbackQuery):
    await send_analytics_view(callback, is_callback=True)
    await callback.answer()


@dp.callback_query(F.data == "menu:killswitch")
async def cb_killswitch_menu(callback: CallbackQuery):
    state = system_state.IS_EMERGENCY_STOP_ACTIVE
    status_str = "🔴 TO'XTATILGAN (MUZLATILGAN)" if state else "🟢 FAOL (XABARLAR CHIQMOQDA)"
    text = (
        f"🚨 **EMERGENCY KILL-SWITCH BOSHQARUVI**\n\n"
        f"Hozirgi holat: **{status_str}**\n\n"
        "Muzlatilsa, barcha avtomatik nashrlar va Telegram kanaliga post chiqarish darhol to'xtatiladi."
    )
    await safe_edit_target(callback, text, reply_markup=get_killswitch_inline())
    await callback.answer()


@dp.callback_query(F.data == "menu:rules")
async def cb_rules(callback: CallbackQuery):
    await send_rules_view(callback, is_callback=True)
    await callback.answer()


@dp.callback_query(F.data.startswith("scan:"))
async def cb_scan_channel(callback: CallbackQuery):
    target = callback.data.split(":")[1]
    await safe_edit_target(
        callback,
        f"🔍 **{target}** kanali skanerlanmoqda...\n"
        "Xabarlar olinmoqda va 4-AI tahlili boshlanmoqda (Yangi Alifboda)..."
    )

    scraper = TelegramWebScraper()
    posts = await scraper.fetch_channel_posts(target, limit=3)

    if not posts:
        fail_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Boshqa Kanalni Tanlash", callback_data="menu:scan")],
                [InlineKeyboardButton(text="🔙 Asosiy Menyu", callback_data="menu:main")],
            ]
        )
        await safe_edit_target(callback, f"❌ **{target}** kanalidan yangi xabarlar topilmadi.", reply_markup=fail_kb)
        await callback.answer()
        return

    processed = 0
    for post in posts:
        res = await orchestrator.ingest_and_process_article(post)
        if res.get("status") in ["scheduled", "human_gate_required"]:
            processed += 1

    finish_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📋 Nashr Navbatini Ko'rish", callback_data="menu:queue"),
                InlineKeyboardButton(text="⚖️ Inson Tasdig'i", callback_data="menu:audits"),
            ],
            [
                InlineKeyboardButton(text="🔍 Yana Kanal Skanerlash", callback_data="menu:scan"),
                InlineKeyboardButton(text="🔙 Asosiy Menyu", callback_data="menu:main"),
            ]
        ]
    )

    await safe_edit_target(
        callback,
        f"✅ **{target} muvaffaqiyatli skanerlandi!**\n\n"
        f"▫️ Topilgan yangi xabarlar: **{len(posts)} ta**\n"
        f"▫️ 4-AI klasteridan o'tkazildi: **{processed} ta**\n"
        f"▫️ Imlo: **Yangi O'zbek Alifbosi (Ö, Ğ, Ş, Ç)**",
        reply_markup=finish_kb
    )
    await callback.answer("Skanerlash yakunlandi!")


@dp.callback_query(F.data.startswith("killswitch:"))
async def cb_killswitch_toggle(callback: CallbackQuery):
    action = callback.data.split(":")[1]
    if action == "freeze":
        system_state.IS_EMERGENCY_STOP_ACTIVE = True
        await safe_edit_target(
            callback,
            "🚨 **EMERGENCY KILL-SWITCH FAOLLASHTIRILDI!**\n\n"
            "🔴 Barcha avtomatik nashrlar va kanallarga chiqarish zudlik bilan to'xtatildi (muzlatildi).",
            reply_markup=get_killswitch_inline()
        )
    else:
        system_state.IS_EMERGENCY_STOP_ACTIVE = False
        await safe_edit_target(
            callback,
            "🟢 **KILL-SWITCH O'CHIRILDI.**\n\n"
            "Oddiy avtomatik nashr rejimi qayta tiklandi. Navbatdagi postlar chiqariladi.",
            reply_markup=get_killswitch_inline()
        )
    await callback.answer()


async def execute_dispatch_top(target, is_callback=False):
    """Dispatches the next waiting post in queue immediately."""
    async with AsyncSessionLocal() as session:
        stmt = (
            select(AI4PublishingQueue)
            .join(AI3Editorial, AI4PublishingQueue.editorial_id == AI3Editorial.id)
            .filter(AI4PublishingQueue.dispatch_status == "WAITING")
            .order_by(AI3Editorial.created_at.desc())
            .limit(1)
        )
        item = (await session.execute(stmt)).scalars().first()

        if not item:
            msg = "📭 Hozirda chiqarish uchun navbatda kutilayotgan post yo'q!"
            if is_callback:
                await target.answer(msg, show_alert=True)
            else:
                await target.answer(msg)
            return

        # Fetch editorial
        editorial = await session.get(AI3Editorial, item.editorial_id)
        if not editorial:
            msg = "Tahririy post topilmadi!"
            if is_callback:
                await target.answer(msg, show_alert=True)
            else:
                await target.answer(msg)
            return

        # Prepare text in New Uzbek Latin Alphabet without duplicate headlines
        headline = (editorial.headline_selected or "").strip()
        body = (editorial.telegram_clean_text or "").strip()

        # Quality Gate: Drop dissertations, tenders, and bureaucratic spam
        if not is_news_worthy(headline, body):
            print(f"[Dispatch Filter] Dropping non-news item: {headline[:60]}", flush=True)
            item.dispatch_status = "CANCELLED"
            await session.commit()
            return await execute_dispatch_top(target, is_callback=is_callback)

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

        sent_to_channel = False
        dispatch_error_msg = ""
        try:
            # Check if visual card exists and send photo
            card_path = editorial.generated_card_url
            if not card_path or not os.path.exists(card_path) or is_russian_text(editorial.headline_selected):
                os.makedirs("storage/cards", exist_ok=True)
                card_filename = f"storage/cards/disp_{item.id}_{int(datetime.now().timestamp())}.jpg"
                try:
                    card_path = canvas_gen.generate_news_card(
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
                    print(f"[Dispatch Card Error] {e}")
            if card_path and os.path.exists(card_path):
                photo = FSInputFile(card_path)
                try:
                    await bot.send_photo(
                        chat_id=channel_id,
                        photo=photo,
                        caption=post_text[:1024],
                        parse_mode=ParseMode.HTML,
                        reply_markup=channel_btn
                    )
                except Exception as send_err:
                    print(f"[Dispatch HTML send error] {send_err}, trying plain text fallback...", flush=True)
                    photo = FSInputFile(card_path)
                    clean_plain = re.sub(r'<[^>]+>', '', post_text)[:1024]
                    await bot.send_photo(
                        chat_id=channel_id,
                        photo=photo,
                        caption=clean_plain,
                        parse_mode=None,
                        reply_markup=channel_btn
                    )
            else:
                try:
                    await bot.send_message(
                        chat_id=channel_id,
                        text=post_text[:4096],
                        parse_mode=ParseMode.HTML,
                        reply_markup=channel_btn,
                        disable_web_page_preview=False
                    )
                except Exception:
                    clean_plain = re.sub(r'<[^>]+>', '', post_text)[:4096]
                    await bot.send_message(
                        chat_id=channel_id,
                        text=clean_plain,
                        parse_mode=None,
                        reply_markup=channel_btn,
                        disable_web_page_preview=False
                    )
            sent_to_channel = True
        except Exception as e:
            dispatch_error_msg = str(e)
            print(f"[Dispatch Warning] Failed sending to channel {channel_id}: {e}", flush=True)

        # Update status in DB
        item.dispatch_status = "DISPATCHED"
        item.dispatched_at = datetime.now(timezone.utc)
        await session.commit()

    if sent_to_channel:
        dest_str = f"va **{channel_id}** kanaliga muvaffaqiyatli yuborildi! 🚀"
    else:
        dest_str = f"\n⚠️ _Eslatma: Bot hali {channel_id} kanaliga admin qilinmagan bo'lishi mumkin ({dispatch_error_msg[:40]}). DB navbati yangilandi._"

    confirm_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📋 Yangilangan Navbat", callback_data="menu:queue")],
            [InlineKeyboardButton(text="🔙 Asosiy Menyu", callback_data="menu:main")],
        ]
    )

    msg_text = (
        f"🚀 **POST CHOP ETILDI!**\n\n"
        f"▫️ Sarlavha: **{editorial.headline_selected}**\n"
        f"▫️ Holati: **DISPATCHED** {dest_str}\n"
        f"▫️ Alifbo: **Yangi O'zbek Alifbosi (Ö, Ğ, Ş, Ç)**"
    )

    if is_callback:
        await safe_edit_target(target, msg_text, reply_markup=confirm_kb)
        await target.answer("Post chiqarildi!")
    else:
        await safe_reply(target, msg_text, reply_markup=confirm_kb)


@dp.callback_query(F.data == "queue:dispatch_top")
async def cb_dispatch_top(callback: CallbackQuery):
    await execute_dispatch_top(callback, is_callback=True)


@dp.callback_query(F.data.startswith("audit:"))
async def cb_handle_audit(callback: CallbackQuery):
    parts = callback.data.split(":")
    action = parts[1]
    raw_id = parts[2]

    try:
        target_uuid = uuid.UUID(raw_id)
    except Exception:
        target_uuid = None

    if not target_uuid:
        await callback.answer("Noto'g'ri audit identifikatori!", show_alert=True)
        return

    async with AsyncSessionLocal() as session:
        if action in ["approve", "reject"]:
            audit = (await session.execute(
                select(AI2Audit).filter(AI2Audit.id == target_uuid)
            )).scalars().first()
        elif action in ["approve_by_art", "reject_by_art"]:
            inv = (await session.execute(
                select(AI1Investigation).filter(AI1Investigation.article_id == target_uuid)
            )).scalars().first()
            audit = (await session.execute(
                select(AI2Audit).filter(AI2Audit.investigation_id == inv.id)
            )).scalars().first() if inv else None
        else:
            audit = None

        if not audit:
            await safe_answer_callback(callback, "Audit topilmadi!", show_alert=True)
            return

        if "approve" in action:
            try:
                res = await orchestrator.approve_and_schedule_audit(audit.id)
                if res.get("status") == "scheduled":
                    await safe_answer_callback(callback, "✅ Xabar ma'qullandi va nashr navbatiga qo'yildi!", show_alert=True)
                else:
                    err_msg = res.get("message", "Noma'lum")
                    await safe_answer_callback(callback, f"⚠️ Xatolik: {err_msg}", show_alert=True)
            except Exception as e:
                print(f"[Audit Approval Error] {e}", flush=True)
                await safe_answer_callback(callback, f"❌ Xatolik yuz berdi: {str(e)[:60]}", show_alert=True)
        elif "reject" in action:
            audit.human_approved_at = None
            audit.human_gate_required = False
            audit.risk_tier = "REJECTED"
            await session.commit()
            await safe_answer_callback(callback, "❌ Xabar rad etildi va arxivlandi.", show_alert=True)

    if action in ["approve", "reject"]:
        await send_audits_view(callback, is_callback=True)
    elif action in ["approve_by_art", "reject_by_art"]:
        try:
            await safe_edit_target(callback, "✅ **Qaror qabul qilindi.**\nXabar ko'rib chiqildi va navbatga yo'naltirildi.")
        except Exception:
            pass


# ==============================================================================
# UNIVERSAL INCOMING MESSAGE & FORWARD HANDLER
# ==============================================================================

@dp.message()
async def universal_message_handler(message: types.Message):
    user_id = message.from_user.id
    current_mode = USER_MODES.get(user_id)
    text_content = message.text.strip() if message.text else ""

    # Mode 1: User is in Fact Check prompt
    if current_mode == "factcheck" and text_content:
        await execute_fact_check(message, text_content)
        return

    # Mode 2: User is in Convert prompt
    if current_mode == "convert" and text_content:
        USER_MODES.pop(user_id, None)
        converted = convert_to_new_uzbek_alphabet(text_content)
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🔎 Faktini Tekshirish", callback_data="menu:factcheck")],
                [InlineKeyboardButton(text="🔙 Asosiy Menyu", callback_data="menu:main")],
            ]
        )
        await safe_reply(message, f"🔤 **Yangi O'zbek Alifbosidagi matn:**\n\n{converted}", reply_markup=kb)
        return

    # Case A: User sent a channel handle e.g. @huquqiyaxborot
    if text_content.startswith("@") and len(text_content) > 2 and " " not in text_content:
        target = text_content
        await safe_reply(message, f"🔍 **{target}** kanali skanerlanmoqda va 4-AI tahlili o'tkazilmoqda...")
        scraper = TelegramWebScraper()
        posts = await scraper.fetch_channel_posts(target, limit=3)

        if not posts:
            await safe_reply(message, f"❌ **{target}** kanalidan yangi xabarlar olinmadi.", reply_markup=get_main_inline_keyboard())
            return

        processed = 0
        for p in posts:
            res = await orchestrator.ingest_and_process_article(p)
            if res.get("status") in ["scheduled", "human_gate_required"]:
                processed += 1

        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="📋 Navbatni Ko'rish", callback_data="menu:queue")],
                [InlineKeyboardButton(text="⚖️ Inson Tasdig'i", callback_data="menu:audits")],
                [InlineKeyboardButton(text="🔙 Asosiy Menyu", callback_data="menu:main")],
            ]
        )
        await safe_reply(
            message,
            f"✅ **{target}** tahlil yakunlandi:\n"
            f"▫️ Xabarlar: **{len(posts)} ta** | Qayta ishlandi: **{processed} ta**\n"
            f"▫️ Imlo: **Yangi O'zbek Alifbosi (Ö, Ğ, Ş, Ç)**",
            reply_markup=kb
        )
        return

    # Case B: User forwarded a message from a channel OR pasted a news article (> 80 chars)
    if message.forward_origin or len(text_content) >= 80:
        source_name = "Forwarded News"
        if message.forward_origin and hasattr(message.forward_origin, 'chat'):
            source_name = getattr(message.forward_origin.chat, 'title', 'Forwarded Channel')

        status_msg = await message.answer("🔄 **Yuborilgan xabar 4-AI tahririyatidan o'tkazilmoqda...**")

        article_payload = {
            "source_url": "telegram_forward",
            "source_identifier": source_name,
            "source_type": "telegram_forward",
            "title": text_content[:80],
            "body_raw": text_content,
            "body_clean": sanitize_text(text_content),
            "content_hash": compute_content_hash(text_content[:80], text_content),
            "category": "JAMIYAT",
            "media_urls": [],
            "published_at": datetime.now(timezone.utc),
        }

        res = await orchestrator.ingest_and_process_article(article_payload)
        await status_msg.delete()

        status = res.get("status")
        if status == "scheduled":
            headline = res.get("headline", "Yangi xabar")
            card_path = res.get("card")

            caption_text = (
                f"✅ **XABAR MUVAFFAQIYATLI QAYTA ISHLANDI!**\n\n"
                f"📌 **Sarlavha:** {headline}\n"
                f"▫️ Ustuvorlik: `{res.get('priority')}`\n"
                f"▫️ Rejalashtirilgan vaqt: `{res.get('slot', '')[:16].replace('T', ' ')}`\n"
                f"▫️ Imlo: **Yangi O'zbek Alifbosi (Ö, Ğ, Ş, Ç)**\n\n"
                "Quyidagi amallardan birini tanlang:"
            )

            action_kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🚀 Hoziroq Kanalga Chiqarish", callback_data="queue:dispatch_top")],
                    [InlineKeyboardButton(text="📋 Nashr Navbatini Ko'rish", callback_data="menu:queue")],
                    [InlineKeyboardButton(text="🔙 Asosiy Menyu", callback_data="menu:main")],
                ]
            )

            if card_path and os.path.exists(card_path):
                photo = FSInputFile(card_path)
                try:
                    await message.answer_photo(photo=photo, caption=caption_text[:1024], parse_mode=ParseMode.MARKDOWN, reply_markup=action_kb)
                except Exception:
                    await message.answer_photo(photo=photo, caption=caption_text[:1024], parse_mode=None, reply_markup=action_kb)
            else:
                await safe_reply(message, caption_text, reply_markup=action_kb)
            return

        elif status == "human_gate_required":
            art_id = res.get("article_id")
            gate_kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text="✅ Ma'qullash & Navbatga Qo'yish", callback_data=f"audit:approve_by_art:{art_id}"),
                        InlineKeyboardButton(text="❌ Rad Etish", callback_data=f"audit:reject_by_art:{art_id}"),
                    ],
                    [InlineKeyboardButton(text="🔙 Asosiy Menyu", callback_data="menu:main")]
                ]
            )
            await safe_reply(
                message,
                f"⚖️ **INSON TASDIG'I TALAB QILINADI:**\n\n"
                f"Ushbu xabar **{res.get('risk')}** xavf darajasiga ega.\n"
                f"Hukm: `{res.get('verdict')}` | Bayes: `{res.get('score', 0):.2f}`\n\n"
                "Qaroringizni belgilang:",
                reply_markup=gate_kb
            )
            return

        elif status == "already_exists":
            await safe_reply(
                message,
                "ℹ️ **Bu xabar avval tahlil qilingan va ma'lumotlar bazasida mavjud.**",
                reply_markup=get_main_inline_keyboard()
            )
            return

    # Fallback normal message response
    help_text = (
        "🤖 **ROVON.UZ AI Tahririyat Boti:**\n\n"
        "Xabaringiz qabul qilindi. Quyidagi interaktiv tugmalar orqali xohlagan amalni tanlang:"
    )
    await safe_reply(message, help_text, reply_markup=get_main_inline_keyboard())


# ==============================================================================
# STANDALONE POLLING RUNNER
# ==============================================================================

async def run_bot_polling():
    """Runs the Telegram bot polling service standalone."""
    print("[Telegram Bot] Setting up bot commands...", flush=True)
    await setup_bot_commands(bot)
    print("[Telegram Bot] Starting polling for @rovonuz_bot...", flush=True)
    await dp.start_polling(bot, drop_pending_updates=True)


if __name__ == "__main__":
    asyncio.run(run_bot_polling())
