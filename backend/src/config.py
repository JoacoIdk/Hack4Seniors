"""Application settings and business rules, read from the environment."""

import logging
import os
import secrets
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

_ = load_dotenv()

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent

# General ----------------------------------------------------------------------

TIMEZONE = ZoneInfo(os.getenv("APP_TIMEZONE", "America/Santiago"))
LOCALES_DIR = Path(os.getenv("LOCALES_PATH", BASE_DIR / "locales"))
DEFAULT_LANGUAGE = os.getenv("DEFAULT_LANGUAGE", "es")
CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]

# Auth -------------------------------------------------------------------------

SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY:
    SECRET_KEY = secrets.token_urlsafe(32)
    logger.warning("SECRET_KEY not set; using a random key (tokens will not survive restarts).")

TOKEN_TTL_HOURS = int(os.getenv("TOKEN_TTL_HOURS", "168"))

# First corporate account, created at startup if it does not exist.
ADMIN_EMAIL = os.getenv("ADMIN_EMAIL")
ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD")

# Points rules -----------------------------------------------------------------

CHAT_POINTS_PER_PERSON_PER_DAY = 2
CHAT_POINTS_LIMIT_PER_PERSON = 10  # until reset_limit is called for the user

PUZZLE_POINTS_PER_SOLVE = 5
PUZZLE_POINTS_DAILY_MAX = 15

# Friends ------------------------------------------------------------------------

# How long a friend QR code is valid after being generated.
FRIEND_CODE_TTL_SECONDS = int(os.getenv("FRIEND_CODE_TTL_SECONDS", "300"))
# Both people must scan each other within this window to become friends.
FRIEND_SCAN_WINDOW_SECONDS = int(os.getenv("FRIEND_SCAN_WINDOW_SECONDS", "900"))


def now() -> datetime:
    """Current time, timezone-aware UTC."""
    return datetime.now(timezone.utc)


def today() -> date:
    """Current calendar day in the platform's timezone (used for daily limits)."""
    return datetime.now(TIMEZONE).date()
