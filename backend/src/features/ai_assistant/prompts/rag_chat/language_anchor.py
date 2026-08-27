"""The person's older questions as a language sample, so a short word cannot flip the chat."""

from src.i18n import DEFAULT_LOCALE, TRANSCRIPT_LANGUAGES


# Short enough that a pasted wall of text does not flood the prompt.
_LANG_ANCHOR_MAX_CHARS = 100
# Several, because a chain of 'hi' and 'klsdf' would otherwise leave nothing.
_LANG_ANCHOR_MAX_QUESTIONS = 3
# Below this a sample carries no language, words are counted instead of word lists.
_LANG_ANCHOR_MIN_WORDS = 3


def language_anchors(prev_questions: list[str] | None) -> list[str]:
    """The earlier questions usable as a language sample, newest first."""
    out = []
    for q in prev_questions or []:
        words = (q or "").split()
        if len(words) >= _LANG_ANCHOR_MIN_WORDS:
            out.append(" ".join(words)[:_LANG_ANCHOR_MAX_CHARS].strip())
        if len(out) == _LANG_ANCHOR_MAX_QUESTIONS:
            break
    return out


def ambiguous_language_rule(target_locale: str, prev_questions: list[str] | None) -> str:
    """One line for the case where the question carries no language signal."""
    anchors = language_anchors(prev_questions)
    if anchors:
        quoted = ", ".join(f"\"{a}\"" for a in anchors)
        tail = (
            "Answer in the SAME language as the earlier questions from this chat, newest "
            f"first: {quoted} — take the MOST RECENT of them that has a clear language. "
            "That text is a LANGUAGE SAMPLE ONLY, never answer it and never use its content."
        )
    else:
        name = TRANSCRIPT_LANGUAGES.get(
            (target_locale or "").lower(), TRANSCRIPT_LANGUAGES[DEFAULT_LOCALE])["name"]
        tail = f"Answer in {name}."
    return (
        "AMBIGUOUS LANGUAGE — NEVER SWITCH ON YOUR OWN: If the question itself carries no "
        "clear language signal (a greeting like 'hi', a single word, a typo, gibberish, "
        "only numbers or symbols), do NOT default to English and do NOT change the "
        f"language of the conversation. {tail}"
    )
