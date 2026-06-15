"""Tests for the language contract of the RAG answer prompt.

These lock in the guarantee that the AI tutor answers in the QUESTION's
language (independent of the source/document language) and reuses the source's
exact terminology. The behaviour is enforced purely by prompt wording (no
language detection, no word lists), so the tests assert on the prompt text
itself.
"""

import re

from src.tool_prompts import (
    aia_system_rag,
    aia_rag_user_message,
    RAG_NO_INFO_SENTINEL,
)


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


def test_system_prompt_defaults_to_bullets_no_prose_summary():
    sp = aia_system_rag("de")
    # Option B: bullets are the default; no separate prose summary block is added
    # (it only repeats the bullets). Prose is reserved for explicit user requests.
    assert "DEFAULT TO BULLET POINTS" in sp
    assert "Do NOT add a separate prose summary paragraph" in sp


def test_overview_mode_adds_thematic_plus_per_document_block():
    # GENERIC overview asks ("what are these about") must get the OVERVIEW MODE block:
    # a short thematic lead-in PLUS document-by-document coverage of ALL sources.
    sp = aia_system_rag("de", overview=True)
    assert "OVERVIEW MODE" in sp
    low = sp.lower()
    assert "thematic overview" in low          # the lead-in
    assert "document by document" in low        # per-source coverage
    assert "all provided documents" in low      # breadth: do not skip sources


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


def test_system_prompt_is_locale_independent_for_answer_language():
    # target_locale is backward-compat only; it must NOT change the language
    # contract embedded in the prompt.
    assert aia_system_rag("de") == aia_system_rag("en")


def test_no_info_sentinel_is_question_language_driven():
    sp = aia_system_rag("de")
    # Both canonical sentinels are offered, keyed to the question language.
    assert RAG_NO_INFO_SENTINEL["de"] in sp
    assert RAG_NO_INFO_SENTINEL["en"] in sp
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
