from __future__ import annotations

from typing import Any


def translate_exact_match(text: str, approved_words: list[dict[str, Any]]) -> dict[str, str | None]:
    """Look up one exact approved vocabulary entry; this is not machine translation."""
    query = (text or "").strip().casefold()
    if not query:
        return {
            "translation": None,
            "message": "Type one word to look for an exact match in the approved local vocabulary.",
        }
    for word in approved_words:
        if not isinstance(word, dict):
            continue
        english = str(word.get("en") or "").strip()
        translation = str(word.get("translation") or "").strip()
        hindi = str(word.get("hindi") or "").strip()
        emoji = word.get("emoji") or "🌱"
        if english and query == english.casefold():
            return {
                "translation": translation or None,
                "source": text.strip(),
                "direction": "English to selected language",
                "emoji": emoji,
            }
        if translation and query == translation.casefold():
            return {
                "translation": english or None,
                "source": text.strip(),
                "direction": "selected language to English",
                "emoji": emoji,
            }
        if hindi and query == hindi.casefold():
            return {
                "translation": translation or None,
                "source": text.strip(),
                "direction": "Hindi to selected language",
                "emoji": emoji,
            }
    return {
        "translation": None,
        "message": "No exact approved word was found. This lookup does not guess or translate phrases.",
    }
