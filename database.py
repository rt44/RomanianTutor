"""SQLite database operations for the Romanian Learning Bot."""

import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


def get_connection() -> sqlite3.Connection:
    """Get a database connection with row factory enabled."""
    from config import DATABASE_PATH
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the database with required tables. Falls back to /tmp if default path fails."""
    import os
    from config import _data_dir
    try:
        conn = get_connection()
    except sqlite3.Error as e:
        # Only fallback when using default path; if user set RAILWAY_VOLUME_MOUNT_PATH, fail
        if os.environ.get("RAILWAY_VOLUME_MOUNT_PATH"):
            raise
        # Fallback: use /tmp so bot can run (data won't persist across restarts)
        import config as cfg
        fallback = Path(os.environ.get("TMPDIR", "/tmp")) / "romanian_bot.db"
        logger.warning("Primary DB path failed (%s), using fallback: %s", e, fallback)
        cfg.DATABASE_PATH = fallback
        conn = sqlite3.connect(fallback)
        conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS translations (
            id INTEGER PRIMARY KEY,
            english TEXT NOT NULL,
            romanian TEXT NOT NULL,
            phonetic TEXT NOT NULL,
            notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY,
            user_message TEXT NOT NULL,
            bot_response TEXT NOT NULL,
            message_type TEXT DEFAULT 'question',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_translations_created
        ON translations(created_at)
    """)

    cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_conversations_created
        ON conversations(created_at)
    """)

    conn.commit()
    conn.close()


def save_translation(english: str, romanian: str, phonetic: str, notes: Optional[str] = None):
    """Save a translation to the database. No-op on failure (never crash)."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO translations (english, romanian, phonetic, notes) VALUES (?, ?, ?, ?)",
            (english, romanian, phonetic, notes)
        )
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        logger.warning("Failed to save translation: %s", e)


def save_conversation(user_msg: str, bot_response: str, msg_type: str = "question"):
    """Save a conversation exchange to the database. No-op on failure."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO conversations (user_message, bot_response, message_type) VALUES (?, ?, ?)",
            (user_msg, bot_response, msg_type)
        )
        conn.commit()
        conn.close()
    except sqlite3.Error as e:
        logger.warning("Failed to save conversation: %s", e)


def get_translations_since(since: datetime) -> list[dict]:
    """Get all translations since a given datetime. Returns [] on failure."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM translations WHERE created_at >= ? ORDER BY created_at ASC",
            (since.isoformat(),)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except sqlite3.Error as e:
        logger.warning("Failed to get translations since: %s", e)
        return []


def get_recent_translations(limit: int = 20) -> list[dict]:
    """Get the most recent translations. Returns [] on failure."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM translations ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except sqlite3.Error as e:
        logger.warning("Failed to get recent translations: %s", e)
        return []


def search_translations(query: str) -> list[dict]:
    """Search translations by English or Romanian text. Returns [] on failure."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        search_term = f"%{query}%"
        cursor.execute(
            """SELECT * FROM translations
               WHERE english LIKE ? OR romanian LIKE ? OR notes LIKE ?
               ORDER BY created_at DESC LIMIT 50""",
            (search_term, search_term, search_term)
        )
        rows = cursor.fetchall()
        conn.close()
        return [dict(row) for row in rows]
    except sqlite3.Error as e:
        logger.warning("Failed to search translations: %s", e)
        return []


def get_stats() -> dict:
    """Get statistics about translations and usage. Returns zeros on failure."""
    empty = {"total_translations": 0, "week_translations": 0, "total_conversations": 0, "first_translation": None}
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM translations")
        total_translations = cursor.fetchone()["count"]
        week_ago = datetime.now() - timedelta(days=7)
        cursor.execute(
            "SELECT COUNT(*) as count FROM translations WHERE created_at >= ?",
            (week_ago.isoformat(),)
        )
        week_translations = cursor.fetchone()["count"]
        cursor.execute("SELECT COUNT(*) as count FROM conversations")
        total_conversations = cursor.fetchone()["count"]
        cursor.execute("SELECT MIN(created_at) as first FROM translations")
        first_row = cursor.fetchone()
        first_translation = first_row["first"] if first_row else None
        conn.close()
        return {
            "total_translations": total_translations,
            "week_translations": week_translations,
            "total_conversations": total_conversations,
            "first_translation": first_translation
        }
    except sqlite3.Error as e:
        logger.warning("Failed to get stats: %s", e)
        return empty
