"""Claude API integration for translations and language help."""

import anthropic
from config import ANTHROPIC_API_KEY

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

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


def translate(english_text: str) -> dict:
    """Translate English text to Romanian with phonetics and notes."""
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=TRANSLATION_SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": f"Translate to Romanian: {english_text}"}
        ]
    )

    response_text = message.content[0].text

    # Parse the JSON response
    import json
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
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=QUESTION_SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": question}
        ]
    )

    return message.content[0].text


def generate_weekly_report(translations: list[dict]) -> str:
    """Generate a weekly progress report from translations."""
    if not translations:
        return "No translations this week. Send me some English phrases to translate!"

    # Format translations for the prompt
    translation_list = "\n".join([
        f"- \"{t['english']}\" → \"{t['romanian']}\" ({t['phonetic']})"
        for t in translations
    ])

    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2048,
        system=WEEKLY_REPORT_SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": f"Create a weekly review for these {len(translations)} translations:\n\n{translation_list}"}
        ]
    )

    return message.content[0].text
