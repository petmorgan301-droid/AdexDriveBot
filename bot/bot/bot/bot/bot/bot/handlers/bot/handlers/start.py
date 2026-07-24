from telegram import Update
from telegram.ext import ContextTypes

from bot.db import get_session
from bot.utils import get_or_create_user

HELP_TEXT = (
    "📁 *AdexDriveBot* \\— your personal Drive, inside Telegram\\.\n\n"
    "*Files*\n"
    "Just send me any document, photo, video, audio or voice note and I'll "
    "save it in your current folder\\.\n\n"
    "*Commands*\n"
    "/ls \\- list the current folder\n"
    "/mkdir `name` \\- create a folder here\n"
    "/cd `name` \\- move into a folder\n"
    "/cd \\.\\. \\- move up one level\n"
    "/pwd \\- show current path\n"
    "/rename `old` `new` \\- rename a file or folder\n"
    "/rm `name` \\- delete a file or folder \\(folders delete everything inside\\)\n"
    "/search `query` \\- search your whole drive by name\n"
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with get_session() as session:
        get_or_create_user(session, update.effective_user)
    await update.message.reply_text(
        "Welcome to AdexDriveBot! 📁\n\n"
        "Send me a file to store it, or use /ls to look around.\n"
        "Type /help to see everything I can do."
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT, parse_mode="MarkdownV2")
