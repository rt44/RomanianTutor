"""APScheduler setup for weekly reports."""

from datetime import datetime, timedelta
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

from config import TIMEZONE, WEEKLY_REPORT_DAY, WEEKLY_REPORT_HOUR, WEEKLY_REPORT_MINUTE
from database import get_translations_since
from translator import generate_weekly_report

# Global reference to the bot application (set during startup)
_bot_app = None
_chat_id = None


def set_bot_app(app, chat_id: int):
    """Set the bot application reference for sending messages."""
    global _bot_app, _chat_id
    _bot_app = app
    _chat_id = chat_id


async def send_weekly_report():
    """Generate and send the weekly report."""
    if not _bot_app or not _chat_id:
        print("Bot app or chat ID not configured for weekly reports")
        return

    # Get translations from the past week
    tz = pytz.timezone(TIMEZONE)
    now = datetime.now(tz)
    week_ago = now - timedelta(days=7)

    translations = get_translations_since(week_ago)

    # Generate the report
    report = generate_weekly_report(translations)

    # Format the header
    start_date = week_ago.strftime("%b %d")
    end_date = now.strftime("%b %d")

    header = f"📚 Week of {start_date}-{end_date} - Your Romanian Progress\n\n"

    if translations:
        header += f"You learned {len(translations)} new phrase{'s' if len(translations) != 1 else ''} this week!\n\n"

    full_report = header + report

    # Send via Telegram
    await _bot_app.bot.send_message(chat_id=_chat_id, text=full_report)


def create_scheduler() -> AsyncIOScheduler:
    """Create and configure the scheduler for weekly reports."""
    tz = pytz.timezone(TIMEZONE)
    scheduler = AsyncIOScheduler(timezone=tz)

    # Schedule weekly report for Friday at 8am
    trigger = CronTrigger(
        day_of_week=WEEKLY_REPORT_DAY,
        hour=WEEKLY_REPORT_HOUR,
        minute=WEEKLY_REPORT_MINUTE,
        timezone=tz
    )

    scheduler.add_job(send_weekly_report, trigger, id="weekly_report")

    return scheduler


async def trigger_weekly_report_now():
    """Manually trigger a weekly report (for /weekly command)."""
    await send_weekly_report()
