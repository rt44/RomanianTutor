"""Claude API integration for translations and language help."""

import json
import logging
import os
import time

import anthropic
from config import ANTHROPIC_API_KEY

logger = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

# Exceptions we retry (transient / rate limit / server overload)
RETRYABLE_EXCEPTIONS = tuple(
    e for e in (
        getattr(anthropic, "RateLimitError", None),
        getattr(anthropic, "InternalServerError", None),
        getattr(anthropic, "APIConnectionError", None),
        getattr(anthropic, "APITimeoutError", None),
        getattr(anthropic, "ServiceUnavailableError", None),
        getattr(anthropic, "OverloadedError", None),
        getattr(anthropic, "DeadlineExceededError", None),
    ) if e is not None
)

# Model fallback chain: if primary fails (e.g. deprecated), try next
MODEL_FALLBACKS = [
    "claude-opus-4-6",
    "claude-opus-4-5-20251101",
    "claude-3-5-sonnet-latest",
]


class TranslationServiceError(Exception):
    """Raised when the translation/LLM service is temporarily unavailable after retries."""

    USER_MESSAGE = "Translation service is temporarily unavailable. Please try again in a moment."


def _get_model() -> str:
    """Primary model; override with ANTHROPIC_MODEL env."""
    return os.environ.get("ANTHROPIC_MODEL") or MODEL_FALLBACKS[0]


def _get_models_to_try() -> list[str]:
    """Ordered list of models to try (env override first, then fallbacks)."""
    override = os.environ.get("ANTHROPIC_MODEL")
    if override:
        return [override] + [m for m in MODEL_FALLBACKS if m != override]
    return MODEL_FALLBACKS.copy()

TRANSLATION_SYSTEM_PROMPT = """You are a Romanian language tutor helping someone learn colloquial, everyday Romanian.

When given English text to translate, respond in this exact JSON format:
{
    "romanian": "the Romanian translation",
    "phonetic": "foh-NEH-tik guide with CAPS for stress",
    "breakdown": [
        {"word": "Romanian word", "meaning": "English meaning"},
        {"word": "Another word", "meaning": "its meaning"}
    ],
    "pattern": "Reusable pattern description, e.g. 'Ne vedem + [time]'",
    "pattern_examples": ["Ne vedem mâine (tomorrow)", "Ne vedem diseară (tonight)"],
    "formality": "casual" or "formal" or "neutral"
}

Guidelines for phonetics:
- Use simple English syllables
- CAPITALIZE the stressed syllable
- Romanian "ă" sounds like "uh" in "but"
- Romanian "â/î" is a deep "uh" sound from the throat
- Romanian "ț" sounds like "ts" in "cats"
- Romanian "ș" sounds like "sh" in "ship"

For breakdown: split into meaningful chunks (not every tiny word)
For pattern: extract the reusable structure if there is one
For pattern_examples: give 2-3 variations using the same pattern

Keep translations natural and conversational, not formal/textbook Romanian."""

QUESTION_SYSTEM_PROMPT = """You are a Romanian language tutor. Answer questions about Romanian grammar, vocabulary, pronunciation, or usage in a clear, helpful way. Include examples when useful. Keep responses concise but informative."""

WEEKLY_REPORT_SYSTEM_PROMPT = """You are a Romanian language tutor creating a weekly review digest.

Given a list of translations from the past week, create a structured review that's easy to scan and study from.

Format your response EXACTLY like this:

━━━ QUICK REVIEW ━━━
[List each phrase in a scannable format:]
• "english" → Romanian (phonetic)
• "english" → Romanian (phonetic)
[...all phrases...]

━━━ PATTERNS YOU LEARNED ━━━
[Group phrases by pattern/theme. Identify 2-4 patterns:]

Pattern: [description]
• example 1
• example 2

━━━ KEY VOCABULARY ━━━
[List 5-10 important words that appeared multiple times or are very useful:]
• word = meaning
• word = meaning

━━━ TIP OF THE WEEK ━━━
[One specific, actionable tip based on what was learned]

Keep it scannable. No fluff. This is a study reference, not a pep talk."""


def _get_response_text(message) -> str:
    """Extract text from Anthropic message content; raise if empty or non-text."""
    if not message.content or len(message.content) == 0:
        raise ValueError("Anthropic API returned empty content")
    block = message.content[0]
    if getattr(block, "type", None) != "text" or not getattr(block, "text", None):
        raise ValueError(f"Unexpected content block type: {getattr(block, 'type', type(block).__name__)}")
    return block.text


def _is_retryable(e: BaseException) -> bool:
    if RETRYABLE_EXCEPTIONS and isinstance(e, RETRYABLE_EXCEPTIONS):
        return True
    # Fallback for older SDK: retry on 429, 5xx
    if hasattr(e, "response") and getattr(e.response, "status_code", None) is not None:
        return e.response.status_code in (429, 500, 502, 503, 504, 529)
    return False


def _is_model_not_found(e: BaseException) -> bool:
    """True if error indicates model not found / deprecated."""
    if getattr(anthropic, "NotFoundError", None) and isinstance(e, anthropic.NotFoundError):
        return True
    code = getattr(getattr(e, "response", None), "status_code", None)
    if code == 404:
        return True
    msg = str(e).lower()
    return "not found" in msg or ("model" in msg and "invalid" in msg)


def _call_api_with_retry(create_message, max_retries: int = 3):
    """Call Anthropic API with exponential backoff on transient errors."""
    last_error = None
    for attempt in range(max_retries):
        try:
            return create_message()
        except BaseException as e:
            if _is_retryable(e):
                last_error = e
                retry_after = None
                if hasattr(e, "response") and getattr(e.response, "headers", None):
                    retry_after = e.response.headers.get("retry-after")
                delay = int(retry_after) if retry_after else min(2 ** attempt, 30)
                logger.warning("Anthropic API transient error (attempt %s/%s), retrying in %ss: %s", attempt + 1, max_retries, delay, e)
                time.sleep(delay)
            else:
                raise
    raise TranslationServiceError(TranslationServiceError.USER_MESSAGE) from last_error


def _call_with_model_fallback(create_message_factory):
    """Try each model in fallback chain; raise only after all fail."""
    models = _get_models_to_try()
    last_error = None
    for model in models:
        try:
            return _call_api_with_retry(lambda: create_message_factory(model))
        except BaseException as e:
            if _is_model_not_found(e):
                logger.warning("Model %s failed (%s), trying fallback...", model, e)
                last_error = e
            else:
                raise
    raise TranslationServiceError(TranslationServiceError.USER_MESSAGE) from last_error


def translate(english_text: str) -> dict:
    """Translate English text to Romanian with phonetics and notes."""
    def create(model):
        return client.messages.create(
            model=model,
            max_tokens=1024,
            system=TRANSLATION_SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": f"Translate to Romanian: {english_text}"}
            ]
        )

    message = _call_with_model_fallback(create)
    response_text = _get_response_text(message)

    # Parse the JSON response
    try:
        # Handle potential markdown code blocks
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]

        result = json.loads(response_text.strip())
        return {
            "romanian": result.get("romanian", ""),
            "phonetic": result.get("phonetic", ""),
            "breakdown": result.get("breakdown", []),
            "pattern": result.get("pattern", ""),
            "pattern_examples": result.get("pattern_examples", []),
            "formality": result.get("formality", "neutral")
        }
    except json.JSONDecodeError:
        # Fallback if JSON parsing fails
        return {
            "romanian": response_text,
            "phonetic": "",
            "breakdown": [],
            "pattern": "",
            "pattern_examples": [],
            "formality": "neutral"
        }


def answer_question(question: str) -> str:
    """Answer a question about Romanian language."""
    def create(model):
        return client.messages.create(
            model=model,
            max_tokens=1024,
            system=QUESTION_SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": question}
            ]
        )

    message = _call_with_model_fallback(create)
    return _get_response_text(message)


def generate_weekly_report(translations: list[dict]) -> str:
    """Generate a weekly progress report from translations."""
    if not translations:
        return "No translations this week. Send me some English phrases to translate!"

    # Format translations for the prompt
    translation_list = "\n".join([
        f"- \"{t['english']}\" → \"{t['romanian']}\" ({t['phonetic']})"
        for t in translations
    ])

    def create(model):
        return client.messages.create(
            model=model,
            max_tokens=2048,
            system=WEEKLY_REPORT_SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": f"Create a weekly review for these {len(translations)} translations:\n\n{translation_list}"}
            ]
        )

    message = _call_with_model_fallback(create)
    return _get_response_text(message)
