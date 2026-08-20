"""Sprachanker: alte Fragen der Person als Sprachprobe, damit "hi" den Chat nicht
ins Englische kippt."""

from src.i18n import DEFAULT_LOCALE, TRANSCRIPT_LANGUAGES


# Kurz genug, dass eine eingefuegte Textwand den Prompt nicht flutet.
_LANG_ANCHOR_MAX_CHARS = 100
# Mehrere, weil eine Kette aus "hi" und "klsdf" sonst nichts uebrig liesse.
_LANG_ANCHOR_MAX_QUESTIONS = 3
# Darunter traegt eine Probe keine Sprache, gezaehlt werden Woerter statt Wortlisten.
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
    """One line telling the model what to do when the question has NO language.

    A greeting, a single word or gibberish carries no signal, and the model falls
    back to English so the chat visibly flips. Earlier questions of the same chat
    are handed over as language SAMPLES, newest first, else the chat language decides.
    """
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
