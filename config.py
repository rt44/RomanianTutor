"""Configuration management for the Romanian Learning Bot."""

import os
from pathlib import Path

# Load .env file if present (for local dev)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Load from environment variables
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
TIMEZONE = os.environ.get("TIMEZONE", "America/Chicago")

# Database path - use persistent storage on Railway if available
# On Railway: set RAILWAY_VOLUME_MOUNT_PATH to a volume path for persistence
_data_dir = Path(os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", "."))
DATABASE_PATH = _data_dir / "romanian_bot.db"

# Weekly report schedule (Friday at 8am)
WEEKLY_REPORT_DAY = "fri"
WEEKLY_REPORT_HOUR = 8
WEEKLY_REPORT_MINUTE = 0

# Validate required config
def validate_config():
    """Ensure all required environment variables are set."""
    missing = []
    if not TELEGRAM_BOT_TOKEN:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not ANTHROPIC_API_KEY:
        missing.append("ANTHROPIC_API_KEY")

    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
