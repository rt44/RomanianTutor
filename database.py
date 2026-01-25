"""SQLite database operations for the Romanian Learning Bot."""

import sqlite3
from datetime import datetime, timedelta
from typing import Optional
from config import DATABASE_PATH


def get_connection() -> sqlite3.Connection:
    """Get a database connection with row factory enabled."""
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initialize the database with required tables."""
    conn = get_connection()
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
    """Save a translation to the database."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO translations (english, romanian, phonetic, notes) VALUES (?, ?, ?, ?)",
        (english, romanian, phonetic, notes)
    )

    conn.commit()
    conn.close()


def save_conversation(user_msg: str, bot_response: str, msg_type: str = "question"):
    """Save a conversation exchange to the database."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "INSERT INTO conversations (user_message, bot_response, message_type) VALUES (?, ?, ?)",
        (user_msg, bot_response, msg_type)
    )

    conn.commit()
    conn.close()


def get_translations_since(since: datetime) -> list[dict]:
    """Get all translations since a given datetime."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM translations WHERE created_at >= ? ORDER BY created_at ASC",
        (since.isoformat(),)
    )

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_recent_translations(limit: int = 20) -> list[dict]:
    """Get the most recent translations."""
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM translations ORDER BY created_at DESC LIMIT ?",
        (limit,)
    )

    rows = cursor.fetchall()
    conn.close()

    return [dict(row) for row in rows]


def search_translations(query: str) -> list[dict]:
    """Search translations by English or Romanian text."""
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


def get_stats() -> dict:
    """Get statistics about translations and usage."""
    conn = get_connection()
    cursor = conn.cursor()

    # Total translations
    cursor.execute("SELECT COUNT(*) as count FROM translations")
    total_translations = cursor.fetchone()["count"]

    # This week's translations
    week_ago = datetime.now() - timedelta(days=7)
    cursor.execute(
        "SELECT COUNT(*) as count FROM translations WHERE created_at >= ?",
        (week_ago.isoformat(),)
    )
    week_translations = cursor.fetchone()["count"]

    # Total conversations
    cursor.execute("SELECT COUNT(*) as count FROM conversations")
    total_conversations = cursor.fetchone()["count"]

    # First translation date
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
