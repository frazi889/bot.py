import os
import logging
from datetime import time
from zoneinfo import ZoneInfo

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Route

from telegram import Update, ChatPermissions
from telegram.ext import (
    Application,
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "telegram-webhook")
PORT = int(os.getenv("PORT", "10000"))
TIMEZONE = os.getenv("TIMEZONE", "Asia/Yangon")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is missing")

if not RENDER_EXTERNAL_URL:
    raise ValueError("RENDER_EXTERNAL_URL is missing")

TZ = ZoneInfo(TIMEZONE)
GROUPS = set()

OPEN_TEXT = (
    "🌅 မင်္ဂလာနံနက်ခင်းပါရှင်\n"
    "Diamond / UC order များကို ယနေ့အတွက် ပြန်လည်လက်ခံပေးနေပါပြီ 💎\n"
    "လိုအပ်တာများကို လွတ်လပ်စွာ မေးမြန်းနိုင်ပါတယ်ရှင် 🙏"
)

CLOSE_TEXT = (
    "🌙 ဒီနေ့အတွက် order လက်ခံမှုကို ယာယီပိတ်ထားပါပြီရှင်\n"
    "မနက်ဖြန်ပြန်လည်ဖွင့်လှစ်ပေးပါမယ် 💎\n"
    "အားပေးမှုအတွက် ကျေးဇူးအများကြီးတင်ပါတယ် 🙏"
)


def get_open_permissions() -> ChatPermissions:
    return ChatPermissions(
        can_send_messages=True,
        can_send_audios=True,
        can_send_documents=True,
        can_send_photos=True,
        can_send_videos=True,
        can_send_video_notes=True,
        can_send_voice_notes=True,
        can_send_polls=True,
        can_send_other_messages=True,
        can_add_web_page_previews=True,
    )


def get_close_permissions() -> ChatPermissions:
    return ChatPermissions(
        can_send_messages=False,
        can_send_audios=False,
        can_send_documents=False,
        can_send_photos=False,
        can_send_videos=False,
        can_send_video_notes=False,
        can_send_voice_notes=False,
        can_send_polls=False,
        can_send_other_messages=False,
        can_add_web_page_previews=False,
    )


async def open_group(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    await context.bot.set_chat_permissions(chat_id=chat_id, permissions=get_open_permissions())
    await context.bot.send_message(chat_id=chat_id, text=OPEN_TEXT)


async def close_group(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    await context.bot.set_chat_permissions(chat_id=chat_id, permissions=get_close_permissions())
    await context.bot.send_message(chat_id=chat_id, text=CLOSE_TEXT)


async def auto_open(context: ContextTypes.DEFAULT_TYPE) -> None:
    for chat_id in list(GROUPS):
        try:
            await open_group(chat_id, context)
        except Exception as e:
            logger.error("Auto open failed for %s: %s", chat_id, e)


async def auto_close(context: ContextTypes.DEFAULT_TYPE) -> None:
    for chat_id in list(GROUPS):
        try:
            await close_group(chat_id, context)
        except Exception as e:
            logger.error("Auto close failed for %s: %s", chat_id, e)


async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    member = await context.bot.get_chat_member(
        update.effective_chat.id,
        update.effective_user.id,
    )
    return member.status in ("administrator", "creator")


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return

    chat = update.effective_chat
    text = (update.message.text or "").strip().upper()

    if chat.type == "private":
        return

    GROUPS.add(chat.id)

    if not await is_admin(update, context):
        return

    if text == "O":
        await open_group(chat.id, context)

    elif text == "C":
        await close_group(chat.id, context)


async def health(request: Request):
    return PlainTextResponse("ok")


async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return JSONResponse({"ok": True})


async def startup():
    await application.initialize()
    await application.start()

    webhook_url = f"{RENDER_EXTERNAL_URL}/telegram/{WEBHOOK_SECRET}"
    await application.bot.set_webhook(webhook_url)

    application.job_queue.run_daily(auto_open, time=time(hour=6, minute=0, tzinfo=TZ))
    application.job_queue.run_daily(auto_close, time=time(hour=20, minute=0, tzinfo=TZ))

    logger.info("Webhook set: %s", webhook_url)


async def shutdown():
    await application.bot.delete_webhook()
    await application.stop()
    await application.shutdown()


application: Application = ApplicationBuilder().token(BOT_TOKEN).build()
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))

app = Starlette(
    routes=[
        Route("/", health, methods=["GET"]),
        Route(f"/telegram/{WEBHOOK_SECRET}", telegram_webhook, methods=["POST"]),
    ],
    on_startup=[startup],
    on_shutdown=[shutdown],
)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
