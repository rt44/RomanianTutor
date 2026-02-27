"""Main Telegram bot logic and handlers."""

import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from config import TELEGRAM_BOT_TOKEN, validate_config
from database import (
    init_db,
    save_translation,
    save_conversation,
    get_recent_translations,
    search_translations,
    get_stats,
)
from translator import translate, answer_question, TranslationServiceError
from scheduler import create_scheduler, set_bot_app, trigger_weekly_report_now

# Set up logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Store the user's chat ID for scheduled messages
USER_CHAT_ID = None


def format_translation_response(english: str, result: dict) -> str:
    """Format a translation result for Telegram."""
    # Header with original English
    response = f'"{english}"\n'
    response += f"↓\n"
    response += f"🇷🇴 {result['romanian']}\n"
    response += f"📖 {result['phonetic']}\n\n"

    # Word breakdown
    if result.get('breakdown'):
        response += "📝 BREAKDOWN\n"
        for item in result['breakdown']:
            response += f"• {item['word']} = {item['meaning']}\n"
        response += "\n"

    # Pattern with examples
    if result.get('pattern'):
        response += f"🔄 PATTERN: {result['pattern']}\n"
        for ex in result.get('pattern_examples', []):
            response += f"• {ex}\n"
        response += "\n"

    # Formality tag
    formality = result.get('formality', 'neutral')
    formality_icons = {'casual': '🎭 Casual', 'formal': '👔 Formal', 'neutral': '➖ Neutral'}
    response += formality_icons.get(formality, '➖ Neutral')

    return response


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    global USER_CHAT_ID
    USER_CHAT_ID = update.effective_chat.id
    set_bot_app(context.application, USER_CHAT_ID)

    await update.message.reply_text(
        "Bună! I'm your Romanian learning companion.\n\n"
        "Send me any English text and I'll translate it to colloquial Romanian "
        "with pronunciation guide.\n\n"
        "Commands:\n"
        "/history - Last 20 translations\n"
        "/search <word> - Search past translations\n"
        "/stats - Your learning stats\n"
        "/weekly - Trigger weekly report\n"
        "/help - Show this message"
    )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command."""
    await update.message.reply_text(
        "How to use this bot:\n\n"
        "📝 Send any English text → Get Romanian translation with phonetics\n\n"
        "Commands:\n"
        "/history - See your last 20 translations\n"
        "/search <word> - Search all past translations\n"
        "/stats - View your learning statistics\n"
        "/weekly - Get your weekly progress report\n"
        "/help - Show this help message\n\n"
        "All your translations are saved permanently!"
    )


async def history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /history command."""
    translations = get_recent_translations(20)

    if not translations:
        await update.message.reply_text("No translations yet! Send me some English text to get started.")
        return

    response = "📚 Your recent translations:\n\n"
    for t in translations:
        response += f"• \"{t['english']}\"\n  → {t['romanian']}\n\n"

    await update.message.reply_text(response)


async def search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /search command."""
    if not context.args:
        await update.message.reply_text("Usage: /search <word or phrase>")
        return

    query = " ".join(context.args)
    results = search_translations(query)

    if not results:
        await update.message.reply_text(f"No translations found matching \"{query}\"")
        return

    response = f"🔍 Results for \"{query}\":\n\n"
    for t in results[:10]:  # Limit to 10 results
        response += f"• \"{t['english']}\"\n  → {t['romanian']} ({t['phonetic']})\n\n"

    if len(results) > 10:
        response += f"...and {len(results) - 10} more results"

    await update.message.reply_text(response)


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /stats command."""
    s = get_stats()

    response = "📊 Your Romanian Learning Stats\n\n"
    response += f"Total translations: {s['total_translations']}\n"
    response += f"This week: {s['week_translations']}\n"
    response += f"Questions asked: {s['total_conversations']}\n"

    if s['first_translation']:
        response += f"\nLearning since: {s['first_translation'][:10]}"

    await update.message.reply_text(response)


async def weekly(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /weekly command - manually trigger weekly report."""
    global USER_CHAT_ID
    USER_CHAT_ID = update.effective_chat.id
    set_bot_app(context.application, USER_CHAT_ID)

    await update.message.reply_text("Generating your weekly report...")
    await trigger_weekly_report_now()


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle regular text messages - translate or answer questions."""
    global USER_CHAT_ID
    USER_CHAT_ID = update.effective_chat.id
    set_bot_app(context.application, USER_CHAT_ID)

    text = update.message.text.strip()

    # Check if it looks like a question about Romanian
    question_indicators = ["?", "how do", "what is", "what's", "why", "when do", "can you explain"]
    is_question = any(indicator in text.lower() for indicator in question_indicators)

    if is_question and any(word in text.lower() for word in ["romanian", "grammar", "word", "phrase", "say", "pronounce"]):
        # Answer as a language question
        response = answer_question(text)
        save_conversation(text, response, "question")
        await update.message.reply_text(response)
    else:
        # Treat as translation request
        result = translate(text)

        # Build notes from breakdown and pattern for storage
        notes_parts = []
        if result.get('breakdown'):
            breakdown_str = ", ".join([f"{b['word']}={b['meaning']}" for b in result['breakdown']])
            notes_parts.append(f"Breakdown: {breakdown_str}")
        if result.get('pattern'):
            notes_parts.append(f"Pattern: {result['pattern']}")
        if result.get('formality'):
            notes_parts.append(f"Formality: {result['formality']}")
        notes = " | ".join(notes_parts) if notes_parts else ""

        # Save to database
        save_translation(text, result['romanian'], result['phonetic'], notes)

        # Format and send response
        response = format_translation_response(text, result)
        await update.message.reply_text(response)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors."""
    err = context.error
    logger.exception("Unhandled error in bot: %s", err)

    if update and update.message:
        if isinstance(err, TranslationServiceError):
            await update.message.reply_text(TranslationServiceError.USER_MESSAGE)
        else:
            await update.message.reply_text(
                "Sorry, something went wrong. Please try again."
            )


def main():
    """Start the bot."""
    # Validate configuration
    validate_config()

    # Initialize database
    init_db()
    logger.info("Database initialized")

    # Create application
    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    # Add handlers
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("history", history))
    app.add_handler(CommandHandler("search", search))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("weekly", weekly))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Add error handler
    app.add_error_handler(error_handler)

    # Create and start scheduler
    scheduler = create_scheduler()
    scheduler.start()
    logger.info("Scheduler started")

    # Start the bot
    logger.info("Starting bot...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
