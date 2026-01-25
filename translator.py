"""Claude API integration for translations and language help."""

import anthropic
from config import ANTHROPIC_API_KEY

client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

TRANSLATION_SYSTEM_PROMPT = """You are a Romanian language tutor helping someone learn colloquial, everyday Romanian.

When given English text to translate:
1. Provide the natural, colloquial Romanian translation (how a native speaker would actually say it)
2. Provide a phonetic pronunciation guide using simple English syllables with CAPS for stressed syllables
3. Add brief usage notes explaining grammar points, formality level, or cultural context

Respond in this exact JSON format:
{
    "romanian": "the Romanian translation",
    "phonetic": "foh-NEH-tik guide",
    "notes": "Brief explanation of grammar, usage, or cultural notes"
}

Guidelines for phonetics:
- Use simple English syllables
- CAPITALIZE the stressed syllable
- Use common English letter combinations (ee, oo, ah, eh, oh)
- Romanian "ă" sounds like "uh" in "but"
- Romanian "â/î" is a deep "uh" sound from the throat
- Romanian "ț" sounds like "ts" in "cats"
- Romanian "ș" sounds like "sh" in "ship"

Keep translations natural and conversational, not formal/textbook Romanian."""

QUESTION_SYSTEM_PROMPT = """You are a Romanian language tutor. Answer questions about Romanian grammar, vocabulary, pronunciation, or usage in a clear, helpful way. Include examples when useful. Keep responses concise but informative."""

WEEKLY_REPORT_SYSTEM_PROMPT = """You are a Romanian language tutor creating a weekly progress report.
Given a list of translations from the past week, create an encouraging summary that:
1. Lists the phrases learned (English → Romanian with phonetic)
2. Identifies patterns (common words, grammar structures that appeared multiple times)
3. Gives 1-2 specific tips based on what was learned

Keep the tone encouraging but not over-the-top. Be specific and helpful."""


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
            "notes": result.get("notes", "")
        }
    except json.JSONDecodeError:
        # Fallback if JSON parsing fails
        return {
            "romanian": response_text,
            "phonetic": "",
            "notes": "Could not parse structured response"
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
            {"role": "user", "content": f"Create a weekly report for these {len(translations)} translations:\n\n{translation_list}"}
        ]
    )

    return message.content[0].text
