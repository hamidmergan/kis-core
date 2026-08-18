"""Tests for the language contract of the RAG answer prompt.

These lock in the guarantee that the AI tutor answers in the QUESTION's
language (independent of the source/document language) and reuses the source's
exact terminology. The behaviour is enforced purely by prompt wording (no
language detection, no word lists), so the tests assert on the prompt text
itself.
"""

import re

from src.features.ai_assistant.prompts.rag_prompts import aia_system_rag, aia_rag_user_message
from src.features.ai_assistant.prompts.refusal_prompts import RAG_NO_INFO_PATTERNS


# ── system prompt: answer language follows the question ──────────────────────

def test_system_prompt_orders_answer_language_to_match_question():
    sp = aia_system_rag("de")
    low = sp.lower()
    # The directive must be present and tie the answer to the *question's*
    # language, not the source/document language.
    assert "same language as the user" in low or "same language as the question" in low
    assert "question" in low


def test_system_prompt_enforces_source_terminology():
    sp = aia_system_rag("de")
    # The TERMINOLOGY rule must still require reusing the source's exact terms.
    assert "TERMINOLOGY" in sp
    assert "source" in sp.lower()
    # No citation chips are injected; the old keyword/chip rule is gone.
    assert "[N, #C" not in sp
    assert "CITATION FORMAT" not in sp


def test_system_prompt_defaults_to_mixed_prose_and_bullets():
    sp = aia_system_rag("de")
    # The default is a MIX of short prose and bullets, decided from the
    # request in ANY language (no keyword list), NOT bullets-only. Pure bullets or pure
    # prose only when the request itself calls for it.
    assert "MIX OF SHORT PROSE AND BULLETS" in sp
    assert "PURE bullets" in sp and "PURE continuous prose" in sp
    # Unrelated topics still stay in separate sentences so each one can be linked to its own
    # passage — but the rule must NOT chop a statement and its qualifiers into a chain of
    # short sentences. That chain was what produced a chip behind every five words.
    assert "KEEP UNRELATED FACTS APART, BUT DO NOT CHOP UP RELATED ONES" in sp
    assert "chain of short sentences that all open the same way" in sp
    # No separate, redundant summary block; the old bullets-only default is gone.
    assert "SEPARATE, redundant summary" in sp
    assert "DEFAULT TO BULLET POINTS" not in sp


def test_overview_mode_is_prose_first_not_a_bullet_dump():
    # A GENERIC overview must be a FLOWING PROSE briefing that weaves the
    # sources together, with bullets/tables only for genuine lists — NOT reduced to a
    # per-document bullet list. The old bullet-forcing wording ("2-4 bullets", "1-2 bullets
    # per source", "document by document") is what made "Überblick" come out as pure bullets.
    sp = aia_system_rag("de", overview=True)
    assert "OVERVIEW MODE" in sp
    low = sp.lower()
    assert "prose" in low                                   # prose is the lead
    assert "narrative" in low or "weave" in low             # woven together, not listed
    assert "every source" in low or "all sources" in low    # breadth: cover every source
    # the bullet-forcing instructions are gone
    assert "2-4 bullets" not in sp
    assert "1-2 bullets" not in sp
    assert "document by document" not in sp.lower()


def test_overview_mode_still_forbids_numbering_sources():
    # Per-document coverage names documents by topic/title, NEVER by index/number —
    # the post-hoc chips do the attribution. The override must keep that contract.
    sp = aia_system_rag("de", overview=True)
    assert "NEVER by a number" in sp
    # Invention/terminology guards survive into the override too.
    assert "invent nothing" in sp.lower()


def test_overview_block_is_off_by_default():
    # SPECIFIC / SCOPE / popup answers stay tight: the default prompt has no OVERVIEW
    # MODE block, so a focused fact question is never inflated into a doc-by-doc tour.
    assert "OVERVIEW MODE" not in aia_system_rag("de")
    assert "OVERVIEW MODE" not in aia_system_rag("de", overview=False)
    # The overview prompt is a strict superset of the default (base unchanged).
    assert aia_system_rag("de", overview=True).startswith(aia_system_rag("de"))


def test_locale_only_decides_the_ambiguous_fallback():
    # The contract for a question WITH a clear language stays locale-independent:
    # the answer follows the question. The configured chat language may only
    # decide the AMBIGUOUS case (greeting, single word, gibberish).
    de, en = aia_system_rag("de"), aia_system_rag("en")
    only_de = [ln for ln in de.splitlines() if ln not in en.splitlines()]
    only_en = [ln for ln in en.splitlines() if ln not in de.splitlines()]
    assert only_de and only_en
    assert all("AMBIGUOUS LANGUAGE" in ln for ln in only_de + only_en)


# ── ambiguous question: keep the previous language, never switch ─────────────

def test_ambiguous_question_falls_back_to_the_previous_question():
    # "hi" / "klsdf" carry no language signal. Without an anchor the model
    # defaults to the system prompt's own language (English) and the chat flips
    # mid-conversation. The previous question of the SAME chat is that anchor.
    sp = aia_system_rag("de", prev_questions=["Was bedeutet Quellenkritik?"])
    assert "AMBIGUOUS LANGUAGE" in sp
    assert "Was bedeutet Quellenkritik?" in sp
    low = sp.lower()
    assert "do not default to english" in low
    # The anchor is a language sample only — it must never be answered itself,
    # the turn stays standalone.
    assert "never answer it" in low


def test_anchor_drops_inputs_that_are_no_language_sample():
    # A chain of ambiguous inputs ("hi", then "klsdf") must not become the
    # anchor itself — handing "hi" over as a sample makes the model answer in
    # English, which is exactly the bug. Only substantial questions qualify.
    line = _ambiguous_line(aia_system_rag("de", prev_questions=[
        "klsdf", "hi", "Was bedeutet das genau?"]))
    assert "Was bedeutet das genau?" in line
    assert "klsdf" not in line and '"hi"' not in line


def test_anchor_falls_back_to_chat_language_when_only_gibberish_precedes():
    only_short = aia_system_rag("de", prev_questions=["hi", "klsdf", "ok"])
    assert _ambiguous_line(only_short) == _ambiguous_line(aia_system_rag("de"))


def test_anchor_lists_the_newest_question_first():
    line = _ambiguous_line(aia_system_rag("de", prev_questions=[
        "was ist neu hier", "was war alt hier"]))
    assert line.index("neu") < line.index("alt")


def _ambiguous_line(sp: str) -> str:
    return next(ln for ln in sp.splitlines() if "AMBIGUOUS LANGUAGE" in ln)


def test_ambiguous_question_without_history_falls_back_to_chat_language():
    # First question of a chat: no previous question exists, so the per-user
    # chat language decides instead of English-by-accident.
    assert "German" in _ambiguous_line(aia_system_rag("de"))
    assert "English" in _ambiguous_line(aia_system_rag("en"))
    # An unknown/missing locale must not produce a broken directive.
    assert "German" in _ambiguous_line(aia_system_rag("xx"))


def test_previous_question_anchor_is_bounded_and_single_line():
    # A pasted wall of text must not blow up the system prompt or break its
    # line structure.
    sp = aia_system_rag("de", prev_questions=["A" * 900 + "\nzweite Zeile"] * 3)
    anchor_line = _ambiguous_line(sp)
    assert len(anchor_line) < 900
    assert "A" * 900 not in anchor_line


def test_empty_previous_questions_behave_like_no_history():
    # Blank/whitespace rows must not produce an empty quoted anchor.
    assert _ambiguous_line(aia_system_rag("de", prev_questions=["", "   "])) == \
        _ambiguous_line(aia_system_rag("de"))


def test_overview_prompt_keeps_the_previous_question_anchor():
    # The overview block is appended to the same base, so the fallback holds for
    # GENERIC answers too.
    sp = aia_system_rag("de", overview=True, prev_questions=["Worum geht es hier?"])
    assert "Worum geht es hier?" in sp
    assert "OVERVIEW MODE" in sp


def test_no_info_shape_is_question_language_driven():
    """Seit 2026-08-16 steht die Luecke am ENDE und der alte Eroeffnungssatz ist raus
    (siehe tests/test_refusal_shape.py). Was der Test prueft, bleibt dasselbe: die
    Sprache entscheidet die FRAGE, nicht die Sprache der Quellen."""
    sp = aia_system_rag("de")
    assert RAG_NO_INFO_PATTERNS["de"] in sp
    assert "in the language of the message" in sp or "SAME LANGUAGE AS THE USER'S QUESTION" in sp
    assert "same language as the user's question" in sp.lower()


# ── user message: the language sandwich around the retrieved context ─────────

def test_user_message_embeds_context_and_question():
    msg = aia_rag_user_message("CONTEXT_BODY", "QUESTION_BODY")
    assert "CONTEXT_BODY" in msg
    assert "QUESTION_BODY" in msg
    assert "Question: QUESTION_BODY" in msg


def test_user_message_sandwiches_language_directive_around_context():
    msg = aia_rag_user_message("CTX", "Who supervises the seminar?")
    ctx_at = msg.index("CTX")
    # A framing instruction comes BEFORE the context ...
    assert "REFERENCE MATERIAL ONLY" in msg
    assert msg.index("REFERENCE MATERIAL ONLY") < ctx_at
    # ... and a reminder comes AFTER it (recency).
    assert "REMINDER" in msg
    assert msg.index("REMINDER") > ctx_at


def test_user_message_reminds_to_match_question_language():
    msg = aia_rag_user_message("CTX", "Q").lower()
    assert "same language as this question" in msg
    assert "another language" in msg  # documents may differ from the question


def test_user_message_reminder_carries_the_language_fallback():
    # The closing REMINDER is the last thing the model reads and it wins on
    # recency. Without the fallback right there, "hi" is read as an English
    # question and the system prompt's rule loses.
    msg = aia_rag_user_message("CTX", "hi", prev_questions=["Was bedeutet das?"])
    assert "Was bedeutet das?" in msg
    assert msg.index("Was bedeutet das?") > msg.index("CTX")


def test_user_message_stays_unchanged_without_an_anchor():
    # First question of a chat: nothing to fall back to, no extra wording.
    assert "LANGUAGE SAMPLE" not in aia_rag_user_message("CTX", "Q")
    assert "LANGUAGE SAMPLE" not in aia_rag_user_message("CTX", "Q", prev_questions=[])


def test_user_message_has_no_citation_injection():
    # Sources are attached post-hoc by semantic attribution, so the user message
    # must NOT ask the model to emit citation chips / keywords.
    msg = aia_rag_user_message("CTX", "Q")
    assert "[N, #C" not in msg
    assert "keyword" not in msg.lower()
    assert "citation" not in msg.lower()


def test_user_message_enforces_table_discipline():
    # Small models habitually add an empty 'Hinweis'/'Note' column. The reminder
    # must forbid that (per-row citations are gone — chips are post-hoc now).
    msg = aia_rag_user_message("CTX", "Q").lower()
    assert "table reminder" in msg
    assert "hinweis" in msg or "note" in msg  # names the forbidden empty column


def test_user_message_has_no_language_specific_wordlist():
    # Guard against regressions that hardcode a language. The directive must be
    # generic ("the language of the Question"), never naming a language to use.
    msg = aia_rag_user_message("CTX", "Q")
    # It may mention German/English only as illustrative source examples in the
    # system prompt, but the USER message must not pin the answer to one.
    assert not re.search(r"answer in (german|english|french)", msg, re.IGNORECASE)
