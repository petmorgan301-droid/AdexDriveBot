from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.db import get_session
from bot.models import FileRecord, Folder
from bot.utils import build_path, get_or_create_user, human_size

MAX_RESULTS = 20


async def search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /search <text>")
        return
    query = " ".join(context.args).strip()
    like = f"%{query}%"

    with get_session() as session:
        user = get_or_create_user(session, update.effective_user)

        folders = (
            session.query(Folder)
            .filter(Folder.user_id == user.id, Folder.name.ilike(like))
            .limit(MAX_RESULTS)
            .all()
        )
        files = (
            session.query(FileRecord)
            .filter(FileRecord.user_id == user.id, FileRecord.name.ilike(like))
            .limit(MAX_RESULTS)
            .all()
        )

        if not folders and not files:
            await update.message.reply_text(f"No results for '{query}'.")
            return

        lines = [f"🔎 Results for *{query}*:", ""]
        buttons = []

        for f in folders:
            path = build_path(session, f)
            lines.append(f"📁 {path}")
            buttons.append([InlineKeyboardButton(f"📁 {path}", callback_data=f"cd:{f.id}")])

        for rec in files:
            parent = session.query(Folder).filter_by(id=rec.folder_id).one()
            path = build_path(session, parent)
            display = f"{path}/{rec.name}".replace("//", "/")
            lines.append(f"📄 {display} ({human_size(rec.size)})")
            buttons.append([InlineKeyboardButton(f"⬇️ {rec.name}", callback_data=f"dl:{rec.id}")])

    text = "\n".join(lines)
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(buttons))
