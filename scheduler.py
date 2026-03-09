"""Weekly report logic. Scheduling is done via the bot's JobQueue in bot.py."""

import asyncio
import logging
from datetime import datetime, timedelta
import pytz

from config import TIMEZONE
from database import get_translations_since
from translator import generate_weekly_report

logger = logging.getLogger(__name__)

# Chat ID for scheduled messages (set when user sends /start or /weekly)
_chat_id = None


def set_chat_id(chat_id: int):
    """Update the chat ID for weekly reports (called on /start and /weekly)."""
    global _chat_id
    _chat_id = chat_id


async def send_weekly_report(context):
    """Generate and send the weekly report. Never crashes - logs and returns on error."""
    if not _chat_id:
        return

    try:
        tz = pytz.timezone(TIMEZONE)
        now = datetime.now(tz)
        week_ago = now - timedelta(days=7)

        translations = get_translations_since(week_ago)
        report = await asyncio.to_thread(generate_weekly_report, translations)

        start_date = week_ago.strftime("%b %d")
        end_date = now.strftime("%b %d")
        header = f"📚 Week of {start_date}-{end_date} - Your Romanian Progress\n\n"
        if translations:
            header += f"You learned {len(translations)} new phrase{'s' if len(translations) != 1 else ''} this week!\n\n"
        full_report = header + report

        await context.bot.send_message(chat_id=_chat_id, text=full_report)
    except Exception as e:
        logger.exception("Weekly report failed: %s", e)


async def trigger_weekly_report_now(context):
    """Manually trigger a weekly report (for /weekly command)."""
    await send_weekly_report(context)
