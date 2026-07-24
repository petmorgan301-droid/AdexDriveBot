import logging

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from bot.config import BOT_TOKEN
from bot.db import init_db
from bot.handlers.files import download_callback, handle_upload, rename, rm
from bot.handlers.folders import cd, cd_callback, ls, mkdir, pwd
from bot.handlers.search import search
from bot.handlers.start import help_command, start

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

ATTACHMENT_FILTER = (
    filters.Document.ALL | filters.PHOTO | filters.VIDEO | filters.AUDIO | filters.VOICE
)


def main() -> None:
    init_db()

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("ls", ls))
    app.add_handler(CommandHandler("pwd", pwd))
    app.add_handler(CommandHandler("mkdir", mkdir))
    app.add_handler(CommandHandler("cd", cd))
    app.add_handler(CommandHandler("rm", rm))
    app.add_handler(CommandHandler("rename", rename))
    app.add_handler(CommandHandler("search", search))

    app.add_handler(MessageHandler(ATTACHMENT_FILTER, handle_upload))

    app.add_handler(CallbackQueryHandler(cd_callback, pattern=r"^cd:\d+$"))
    app.add_handler(CallbackQueryHandler(download_callback, pattern=r"^dl:\d+$"))

    logger.info("AdexDriveBot starting (polling mode)...")
    app.run_polling(allowed_updates=["message", "callback_query"])


if __name__ == "__main__":
    main()
