import os
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"

DATA_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
ADMIN_CHAT_ID = int(os.environ["ADMIN_CHAT_ID"])

CHAT_MODEL = os.getenv("CHAT_MODEL", "claude-sonnet-4-6")
MAX_CHAT_HISTORY = int(os.getenv("MAX_CHAT_HISTORY", "20"))

CYCLE_LENGTH = int(os.getenv("CYCLE_LENGTH", "28"))
LAST_PERIOD_START = os.getenv("LAST_PERIOD_START", "2026-01-28")

REMINDER_HOUR = int(os.getenv("REMINDER_HOUR", "9"))
TIMEZONE = ZoneInfo(os.getenv("TIMEZONE", "Asia/Tehran"))

DB_PATH = DATA_DIR / "lunaris.db"
