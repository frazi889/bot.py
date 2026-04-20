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
    CommandHandler,
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

# memory only; redeploy/restart ဖြစ်ရင် ပြန်ပျောက်နိုင်တယ်
GROUP_SETTINGS = {}

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
    await context.bot.set_chat_permissions(
        chat_id=chat_id,
        permissions=get_open_permissions(),
    )
    await context.bot.send_message(
        chat_id=chat_id,
        text=OPEN_TEXT,
    )


async def close_group(chat_id: int, context: ContextTypes.DEFAULT_TYPE) -> None:
    await context.bot.set_chat_permissions(
        chat_id=chat_id,
        permissions=get_close_permissions(),
    )
    await context.bot.send_message(
        chat_id=chat_id,
        text=CLOSE_TEXT,
    )


async def auto_open(context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = context.job.chat_id
    if not chat_id:
        return

    try:
        await open_group(chat_id, context)
        logger.info("Auto opened group: %s", chat_id)
    except Exception as e:
        logger.error("Auto open failed for %s: %s", chat_id, e)


async def auto_close(context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = context.job.chat_id
    if not chat_id:
        return

    try:
        await close_group(chat_id, context)
        logger.info("Auto closed group: %s", chat_id)
    except Exception as e:
        logger.error("Auto close failed for %s: %s", chat_id, e)


async def is_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not update.effective_chat or not update.effective_user:
        return False

    member = await context.bot.get_chat_member(
        update.effective_chat.id,
        update.effective_user.id,
    )
    return member.status in ("administrator", "creator")


def remove_group_jobs(chat_id: int) -> None:
    for job in application.job_queue.get_jobs_by_name(f"open_{chat_id}"):
        job.schedule_removal()

    for job in application.job_queue.get_jobs_by_name(f"close_{chat_id}"):
        job.schedule_removal()


def schedule_group(chat_id: int, open_hour: int, close_hour: int) -> None:
    remove_group_jobs(chat_id)

    application.job_queue.run_daily(
        auto_open,
        time=time(hour=open_hour, minute=0, tzinfo=TZ),
        chat_id=chat_id,
        name=f"open_{chat_id}",
    )

    application.job_queue.run_daily(
        auto_close,
        time=time(hour=close_hour, minute=0, tzinfo=TZ),
        chat_id=chat_id,
        name=f"close_{chat_id}",
    )

    GROUP_SETTINGS[chat_id] = {
        "open_hour": open_hour,
        "close_hour": close_hour,
    }

    logger.info(
        "Scheduled group %s: open=%02d:00 close=%02d:00",
        chat_id,
        open_hour,
        close_hour,
    )


def ensure_group_registered(chat_id: int) -> None:
    if chat_id not in GROUP_SETTINGS:
        schedule_group(chat_id, 6, 20)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.info(
        "START command received: chat_id=%s text=%s",
        update.effective_chat.id if update.effective_chat else None,
        update.message.text if update.message else None,
    )

    if not update.message or not update.effective_chat:
        return

    if update.effective_chat.type != "private":
        ensure_group_registered(update.effective_chat.id)

    await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=(
            "🤖 Bot အသုံးပြုပုံ\n\n"
            "O = Group ဖွင့်\n"
            "C = Group ပိတ်\n\n"
            "/settime 6 20\n"
            "အဓိပ္ပါယ် = မနက် 6 နာရီဖွင့် ည 8 နာရီပိတ်\n\n"
            "/showtime = လက်ရှိ auto time ကြည့်\n"
            "/start = အသုံးပြုပုံပြန်ကြည့်\n\n"
            "မှတ်ချက်:\n"
            "- Group admin ပဲ သုံးလို့ရပါတယ်\n"
            "- Default time က 6 AM to 8 PM ပါ"
        ),
    )


async def showtime(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return

    if update.effective_chat.type == "private":
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="ဒီ command ကို group ထဲမှာပဲ သုံးပါ။",
        )
        return

    chat_id = update.effective_chat.id
    ensure_group_registered(chat_id)

    cfg = GROUP_SETTINGS[chat_id]
    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            "⏰ Current Auto Time\n"
            f"Open: {cfg['open_hour']:02d}:00\n"
            f"Close: {cfg['close_hour']:02d}:00"
        ),
    )


async def settime(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return

    if update.effective_chat.type == "private":
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="ဒီ command ကို group ထဲမှာပဲ သုံးပါ။",
        )
        return

    if not await is_admin(update, context):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="ဒီ command ကို group admin ပဲ သုံးလို့ရပါတယ်။",
        )
        return

    if len(context.args) != 2:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="ဥပမာ: /settime 6 20",
        )
        return

    try:
        open_hour = int(context.args[0])
        close_hour = int(context.args[1])
    except ValueError:
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Hour ကို number နဲ့ရေးပါ။ ဥပမာ: /settime 6 20",
        )
        return

    if not (0 <= open_hour <= 23 and 0 <= close_hour <= 23):
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text="Hour က 0 နဲ့ 23 ကြား ဖြစ်ရမယ်။",
        )
        return

    chat_id = update.effective_chat.id
    schedule_group(chat_id, open_hour, close_hour)

    await context.bot.send_message(
        chat_id=chat_id,
        text=(
            "✅ Auto time ပြောင်းပြီးပါပြီ\n"
            f"From {open_hour:02d}:00 To {close_hour:02d}:00"
        ),
    )


async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.effective_chat:
        return

    chat = update.effective_chat
    text = (update.message.text or "").strip().upper()

    if chat.type == "private":
        return

    ensure_group_registered(chat.id)

    if text not in ("O", "C"):
        return

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
    logger.info("Webhook update received: %s", data.get("update_id"))

    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return JSONResponse({"ok": True})


async def startup():
    await application.initialize()
    await application.start()

    webhook_url = f"{RENDER_EXTERNAL_URL}/telegram/{WEBHOOK_SECRET}"
    await application.bot.delete_webhook(drop_pending_updates=True)
    await application.bot.set_webhook(webhook_url)

    logger.info("Webhook set: %s", webhook_url)


async def shutdown():
    await application.bot.delete_webhook()
    await application.stop()
    await application.shutdown()


application: Application = ApplicationBuilder().token(BOT_TOKEN).build()

application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("showtime", showtime))
application.add_handler(CommandHandler("settime", settime))
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
