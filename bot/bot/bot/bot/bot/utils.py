from sqlalchemy.orm import Session

from bot.models import Folder, User


def get_or_create_user(session: Session, telegram_user) -> User:
    user = session.query(User).filter_by(telegram_id=telegram_user.id).one_or_none()
    if user:
        return user

    user = User(telegram_id=telegram_user.id, username=telegram_user.username)
    session.add(user)
    session.flush()  # get user.id without committing

    root = Folder(user_id=user.id, parent_id=None, name="/")
    session.add(root)
    session.flush()

    user.current_folder_id = root.id
    session.flush()
    return user


def get_root_folder(session: Session, user: User) -> Folder:
    return (
        session.query(Folder)
        .filter_by(user_id=user.id, parent_id=None)
        .one()
    )


def get_current_folder(session: Session, user: User) -> Folder:
    folder = None
    if user.current_folder_id is not None:
        folder = (
            session.query(Folder)
            .filter_by(id=user.current_folder_id, user_id=user.id)
            .one_or_none()
        )
    if folder is None:
        folder = get_root_folder(session, user)
        user.current_folder_id = folder.id
    return folder


def build_path(session: Session, folder: Folder) -> str:
    parts = []
    node = folder
    while node is not None:
        if node.parent_id is None:
            parts.append("")  # root marker, produces a leading slash
            node = None
        else:
            parts.append(node.name)
            node = session.query(Folder).filter_by(id=node.parent_id).one()
    parts.reverse()
    path = "/".join(parts)
    return path if path else "/"


def human_size(num_bytes) -> str:
    if num_bytes is None:
        return "unknown size"
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"
