import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.environ.get("BOT_TOKEN")
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./adexdrive.db")
STORAGE_CHAT_ID = os.environ.get("STORAGE_CHAT_ID")

# Railway/Heroku-style Postgres URLs sometimes come as "postgres://",
# but SQLAlchemy 2.x + psycopg2 needs "postgresql://".
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

if not BOT_TOKEN:
    raise RuntimeError(
        "BOT_TOKEN is not set. Add it to your .env file (local) "
        "or your Railway service variables (production)."
    )

if not STORAGE_CHAT_ID:
    raise RuntimeError(
        "STORAGE_CHAT_ID is not set. Create a private channel, add the bot "
        "as admin, and set STORAGE_CHAT_ID to that channel's id. See README."
    )

STORAGE_CHAT_ID = int(STORAGE_CHAT_ID)
