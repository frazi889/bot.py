import logging
import os

from telegram import Update, ChatPermissions
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is missing")


async def is_group_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    chat = update.effective_chat

    if not user or not chat:
        return False

    member = await context.bot.get_chat_member(chat.id, user.id)
    return member.status in ("administrator", "creator")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(
            "အသုံးပြုပုံ:\n"
            "O = Group ဖွင့်\n"
            "C = Group ပိတ်\n\n"
            "Admin ပဲ သုံးလို့ရပါတယ်။"
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message:
        await update.message.reply_text(
            "ဒီ bot ကို group ထဲထည့်ပြီး admin ပေးပါ။\n"
            "ပြီးရင် admin တစ်ယောက်က\n"
            "O ပို့ရင် ဖွင့်မယ်\n"
            "C ပို့ရင် ပိတ်မယ်"
        )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.effective_chat:
        return

    chat = update.effective_chat
    text = (update.message.text or "").strip().upper()

    # private chat မှာမလုပ်ဘူး
    if chat.type == "private":
        await update.message.reply_text("ဒီ bot ကို group ထဲမှာပဲ သုံးပါ။")
        return

    # O / C မဟုတ်ရင် ignore
    if text not in ("O", "C"):
        return

    # admin မဟုတ်ရင် ignore
    if not await is_group_admin(update, context):
        return

    try:
        if text == "O":
            permissions = ChatPermissions(
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
                can_change_info=False,
                can_invite_users=True,
                can_pin_messages=False,
                can_manage_topics=False,
            )

            await context.bot.set_chat_permissions(
                chat_id=chat.id,
                permissions=permissions,
            )
            await update.message.reply_text("🔓 Group ဖွင့်ပြီးပါပြီ")

        elif text == "C":
            permissions = ChatPermissions(
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
                can_change_info=False,
                can_invite_users=False,
                can_pin_messages=False,
                can_manage_topics=False,
            )

            await context.bot.set_chat_permissions(
                chat_id=chat.id,
                permissions=permissions,
            )
            await update.message.reply_text("🔒 Group ပိတ်ပြီးပါပြီ")

    except Exception as e:
        logging.exception("Failed to change group permissions")
        await update.message.reply_text(f"Error: {e}")


def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
