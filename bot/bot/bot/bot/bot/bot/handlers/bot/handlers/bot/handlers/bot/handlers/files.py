from sqlalchemy.exc import IntegrityError
from telegram import Update
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from bot.config import STORAGE_CHAT_ID
from bot.db import get_session
from bot.models import FileRecord, Folder
from bot.utils import get_current_folder, get_or_create_user


def _unique_file_name(session, folder_id: int, base_name: str) -> str:
    name = base_name
    counter = 1
    while session.query(FileRecord).filter_by(folder_id=folder_id, name=name).one_or_none():
        if "." in base_name:
            stem, ext = base_name.rsplit(".", 1)
            name = f"{stem} ({counter}).{ext}"
        else:
            name = f"{base_name} ({counter})"
        counter += 1
    return name


def _extract_attachment(message):
    """Returns (file_id, size, kind, default_name) for the first supported
    attachment on a message, or None if there isn't one."""
    if message.document:
        d = message.document
        return d.file_id, d.file_size, "document", d.file_name or f"file_{message.message_id}"
    if message.photo:
        p = message.photo[-1]
        return p.file_id, p.file_size, "photo", f"photo_{message.message_id}.jpg"
    if message.video:
        v = message.video
        return v.file_id, v.file_size, "video", v.file_name or f"video_{message.message_id}.mp4"
    if message.audio:
        a = message.audio
        return a.file_id, a.file_size, "audio", a.file_name or f"audio_{message.message_id}.mp3"
    if message.voice:
        v = message.voice
        return v.file_id, v.file_size, "voice", f"voice_{message.message_id}.ogg"
    return None


async def handle_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    attachment = _extract_attachment(update.message)
    if attachment is None:
        return
    file_id, size, kind, default_name = attachment

    # Duplicate the message into the private storage channel so we have a
    # permanent copy independent of the user's chat history.
    try:
        copied = await context.bot.copy_message(
            chat_id=STORAGE_CHAT_ID,
            from_chat_id=update.effective_chat.id,
            message_id=update.message.message_id,
        )
    except TelegramError as e:
        await update.message.reply_text(
            "⚠️ Couldn't save that — is the bot an admin of the storage channel? "
            f"({e})"
        )
        return

    with get_session() as session:
        user = get_or_create_user(session, update.effective_user)
        folder = get_current_folder(session, user)
        name = _unique_file_name(session, folder.id, default_name)

        record = FileRecord(
            user_id=user.id,
            folder_id=folder.id,
            name=name,
            telegram_file_id=file_id,
            telegram_message_id=copied.message_id,
            file_type=kind,
            size=size,
        )
        session.add(record)

    await update.message.reply_text(f"✅ Saved as {name}")


async def download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    file_id = int(query.data.split(":", 1)[1])

    with get_session() as session:
        user = get_or_create_user(session, update.effective_user)
        record = session.query(FileRecord).filter_by(id=file_id, user_id=user.id).one_or_none()

    if record is None:
        await query.answer("That file no longer exists.", show_alert=True)
        return

    try:
        await context.bot.copy_message(
            chat_id=update.effective_chat.id,
            from_chat_id=STORAGE_CHAT_ID,
            message_id=record.telegram_message_id,
        )
    except TelegramError:
        await query.answer("Couldn't retrieve that file.", show_alert=True)


def _delete_folder_recursive(session, user_id: int, folder: Folder, bot_delete_fns):
    files = session.query(FileRecord).filter_by(user_id=user_id, folder_id=folder.id).all()
    for f in files:
        bot_delete_fns.append(f.telegram_message_id)
        session.delete(f)

    subfolders = session.query(Folder).filter_by(user_id=user_id, parent_id=folder.id).all()
    for sub in subfolders:
        _delete_folder_recursive(session, user_id, sub, bot_delete_fns)
        session.delete(sub)


async def rm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text("Usage: /rm <name>")
        return
    name = " ".join(context.args).strip()

    to_delete_messages = []
    with get_session() as session:
        user = get_or_create_user(session, update.effective_user)
        folder = get_current_folder(session, user)

        file_match = (
            session.query(FileRecord)
            .filter_by(user_id=user.id, folder_id=folder.id, name=name)
            .one_or_none()
        )
        folder_match = (
            session.query(Folder)
            .filter_by(user_id=user.id, parent_id=folder.id, name=name)
            .one_or_none()
        )

        if file_match is None and folder_match is None:
            await update.message.reply_text(f"Nothing named '{name}' here.")
            return

        if file_match is not None:
            to_delete_messages.append(file_match.telegram_message_id)
            session.delete(file_match)
        else:
            _delete_folder_recursive(session, user.id, folder_match, to_delete_messages)
            session.delete(folder_match)

    for msg_id in to_delete_messages:
        try:
            await context.bot.delete_message(chat_id=STORAGE_CHAT_ID, message_id=msg_id)
        except TelegramError:
            pass  # best-effort; DB record is already gone either way

    await update.message.reply_text(f"🗑️ Deleted '{name}'")


async def rename(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /rename <old name> <new name>")
        return
    old_name, new_name = context.args[0], " ".join(context.args[1:]).strip()

    with get_session() as session:
        user = get_or_create_user(session, update.effective_user)
        folder = get_current_folder(session, user)

        file_match = (
            session.query(FileRecord)
            .filter_by(user_id=user.id, folder_id=folder.id, name=old_name)
            .one_or_none()
        )
        folder_match = (
            session.query(Folder)
            .filter_by(user_id=user.id, parent_id=folder.id, name=old_name)
            .one_or_none()
        )

        target = file_match or folder_match
        if target is None:
            await update.message.reply_text(f"Nothing named '{old_name}' here.")
            return

        target.name = new_name
        try:
            session.flush()
        except IntegrityError:
            session.rollback()
            await update.message.reply_text(f"'{new_name}' is already taken here.")
            return

    await update.message.reply_text(f"✏️ Renamed '{old_name}' to '{new_name}'")
