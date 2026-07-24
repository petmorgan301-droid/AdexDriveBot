from sqlalchemy.exc import IntegrityError
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from bot.db import get_session
from bot.models import FileRecord, Folder
from bot.utils import build_path, get_current_folder, get_or_create_user, human_size

INVALID_NAME_CHARS = ("/", "\\")


def _valid_name(name: str) -> bool:
    name = name.strip()
    if not name or name in (".", ".."):
        return False
    return not any(ch in name for ch in INVALID_NAME_CHARS)


def _render_listing(session, user, folder: Folder):
    path = build_path(session, folder)
    subfolders = (
        session.query(Folder)
        .filter_by(user_id=user.id, parent_id=folder.id)
        .order_by(Folder.name)
        .all()
    )
    files = (
        session.query(FileRecord)
        .filter_by(user_id=user.id, folder_id=folder.id)
        .order_by(FileRecord.name)
        .all()
    )

    lines = [f"📂 *{path}*", ""]
    buttons = []

    if folder.parent_id is not None:
        buttons.append([InlineKeyboardButton("⬆️ ..", callback_data=f"cd:{folder.parent_id}")])

    if not subfolders and not files:
        lines.append("_This folder is empty._")

    for sub in subfolders:
        lines.append(f"📁 {sub.name}")
        buttons.append([InlineKeyboardButton(f"📁 {sub.name}", callback_data=f"cd:{sub.id}")])

    for f in files:
        lines.append(f"📄 {f.name} ({human_size(f.size)})")
        buttons.append([InlineKeyboardButton(f"⬇️ {f.name}", callback_data=f"dl:{f.id}")])

    text = "\n".join(lines)
    markup = InlineKeyboardMarkup(buttons) if buttons else None
    return text, markup


async def ls(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with get_session() as session:
        user = get_or_create_user(session, update.effective_user)
        folder = get_current_folder(session, user)
        text, markup = _render_listing(session, user, folder)
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=markup)


async def pwd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    with get_session() as session:
        user = get_or_create_user(session, update.effective_user)
        folder = get_current_folder(session, user)
        path = build_path(session, folder)
    await update.message.reply_text(f"📍 {path}")


async def mkdir(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /mkdir <folder name>")
        return
    name = " ".join(context.args).strip()
    if not _valid_name(name):
        await update.message.reply_text("That folder name isn't allowed.")
        return

    with get_session() as session:
        user = get_or_create_user(session, update.effective_user)
        folder = get_current_folder(session, user)
        new_folder = Folder(user_id=user.id, parent_id=folder.id, name=name)
        session.add(new_folder)
        try:
            session.flush()
        except IntegrityError:
            session.rollback()
            await update.message.reply_text(f"A folder named '{name}' already exists here.")
            return

    await update.message.reply_text(f"📁 Created folder: {name}")


async def cd(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /cd <folder name>  (or /cd .. to go up)")
        return
    target = " ".join(context.args).strip()

    with get_session() as session:
        user = get_or_create_user(session, update.effective_user)
        folder = get_current_folder(session, user)

        if target == "..":
            if folder.parent_id is None:
                await update.message.reply_text("You're already at the root.")
                return
            user.current_folder_id = folder.parent_id
            new_path = build_path(session, session.query(Folder).get(folder.parent_id))
            await update.message.reply_text(f"📍 {new_path}")
            return

        sub = (
            session.query(Folder)
            .filter_by(user_id=user.id, parent_id=folder.id, name=target)
            .one_or_none()
        )
        if sub is None:
            await update.message.reply_text(f"No folder named '{target}' here.")
            return

        user.current_folder_id = sub.id
        new_path = build_path(session, sub)
    await update.message.reply_text(f"📍 {new_path}")


async def cd_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    folder_id = int(query.data.split(":", 1)[1])

    with get_session() as session:
        user = get_or_create_user(session, update.effective_user)
        folder = session.query(Folder).filter_by(id=folder_id, user_id=user.id).one_or_none()
        if folder is None:
            await query.edit_message_text("That folder no longer exists.")
            return
        user.current_folder_id = folder.id
        text, markup = _render_listing(session, user, folder)

    await query.edit_message_text(text, parse_mode="Markdown", reply_markup=markup)
