"""The tutor answers in the language of the question, checked in the prompt text."""

import re

from src.features.ai_assistant.prompts.rag_chat import aia_system_rag, aia_rag_user_message


# ── system prompt: answer language follows the question ──────────────────────

def test_system_prompt_orders_answer_language_to_match_question():
    sp = aia_system_rag("de")
    low = sp.lower()
    # The instruction binds the answer to the language of the question.
    assert "language of the question" in low
    assert "question" in low


def test_system_prompt_enforces_source_terminology():
    sp = aia_system_rag("de")
    # The TERMINOLOGY rule must still require reusing the source's exact terms.
    assert "exact technical terms" in sp
    assert "source" in sp.lower()
    # No citation chips are injected; the old keyword/chip rule is gone.
    assert "[N, #C" not in sp
    assert "CITATION FORMAT" not in sp


def test_system_prompt_defaults_to_mixed_prose_and_bullets():
    sp = aia_system_rag("de")
    # The default is a mixture, not only bullet lists.
    assert "Mix short prose and bullets" in sp
    # Separate topics stay separate sentences, but no run-on chain.
    assert "no closing summary" in sp
    assert "DEFAULT TO BULLET POINTS" not in sp


def test_overview_mode_is_prose_first_not_a_bullet_dump():
    # An overview is prose, not one bullet per document.
    sp = aia_system_rag("de", overview=True)
    assert "## Overview mode" in sp
    low = sp.lower()
    assert "prose" in low                                   # prose is the lead
    assert "narrative" in low or "weave" in low             # woven together, not listed
    assert "every source" in low or "all sources" in low    # breadth: cover every source
    # the bullet-forcing instructions are gone
    assert "2-4 bullets" not in sp
    assert "1-2 bullets" not in sp
    assert "document by document" not in sp.lower()


def test_overview_mode_still_forbids_numbering_sources():
    # Documents are named by topic, never by a number.
    sp = aia_system_rag("de", overview=True)
    assert "NEVER by a number" in sp
    # Invention/terminology guards survive into the override too.
    assert "invent nothing" in sp.lower()


def test_overview_block_is_off_by_default():
    # A specific question is never inflated into a tour of the documents.
    assert "## Overview mode" not in aia_system_rag("de")
    assert "## Overview mode" not in aia_system_rag("de", overview=False)
    # The overview block leaves out exactly the entry limit.
    knapp, breit = aia_system_rag("de"), aia_system_rag("de", overview=True)
    nur_knapp = [ln for ln in knapp.splitlines() if ln not in breit.splitlines()]
    assert len(nur_knapp) == 1 and "AT MOST FIVE" in nur_knapp[0]
    assert breit.endswith("- Be thorough, state each fact once, invent nothing.\n")


def test_locale_only_decides_the_ambiguous_fallback():
    # With a clear language the answer follows the question, not the setting.
    de, en = aia_system_rag("de"), aia_system_rag("en")
    only_de = [ln for ln in de.splitlines() if ln not in en.splitlines()]
    only_en = [ln for ln in en.splitlines() if ln not in de.splitlines()]
    assert only_de and only_en
    assert all("AMBIGUOUS LANGUAGE" in ln for ln in only_de + only_en)


# ── ambiguous question: keep the previous language, never switch ─────────────

def test_ambiguous_question_falls_back_to_the_previous_question():
    # Without a language signal the previous question serves as the anchor.
    sp = aia_system_rag("de", prev_questions=["Was bedeutet Quellenkritik?"])
    assert "AMBIGUOUS LANGUAGE" in sp
    assert "Was bedeutet Quellenkritik?" in sp
    low = sp.lower()
    assert "do not default to english" in low
    # The anchor is only a language sample and is never answered itself.
    assert "never answer it" in low


def test_anchor_drops_inputs_that_are_no_language_sample():
    # Only content-bearing questions work as an anchor.
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
    # For the first question the configured chat language decides.
    assert "German" in _ambiguous_line(aia_system_rag("de"))
    assert "English" in _ambiguous_line(aia_system_rag("en"))
    # An unknown/missing locale must not produce a broken directive.
    assert "German" in _ambiguous_line(aia_system_rag("xx"))


def test_previous_question_anchor_is_bounded_and_single_line():
    # A pasted block of text must not blow up the prompt.
    sp = aia_system_rag("de", prev_questions=["A" * 900 + "\nzweite Zeile"] * 3)
    anchor_line = _ambiguous_line(sp)
    assert len(anchor_line) < 900
    assert "A" * 900 not in anchor_line


def test_empty_previous_questions_behave_like_no_history():
    # Blank/whitespace rows must not produce an empty quoted anchor.
    assert _ambiguous_line(aia_system_rag("de", prev_questions=["", "   "])) == \
        _ambiguous_line(aia_system_rag("de"))


def test_overview_prompt_keeps_the_previous_question_anchor():
    # The fallback applies to overview answers too.
    sp = aia_system_rag("de", overview=True, prev_questions=["Worum geht es hier?"])
    assert "Worum geht es hier?" in sp
    assert "## Overview mode" in sp


def test_no_info_shape_is_question_language_driven():
    """The question decides the language, not the language of the sources."""
    sp = aia_system_rag("de")
    assert "## Answer format" in sp
    assert "language of the QUESTION" in sp


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
    # The closing hint weighs the most and carries the fallback.
    msg = aia_rag_user_message("CTX", "hi", prev_questions=["Was bedeutet das?"])
    assert "Was bedeutet das?" in msg
    assert msg.index("Was bedeutet das?") > msg.index("CTX")


def test_user_message_stays_unchanged_without_an_anchor():
    # First question of a chat: nothing to fall back to, no extra wording.
    assert "LANGUAGE SAMPLE" not in aia_rag_user_message("CTX", "Q")
    assert "LANGUAGE SAMPLE" not in aia_rag_user_message("CTX", "Q", prev_questions=[])


def test_user_message_has_no_citation_injection():
    # The citations come afterwards, the prompt must not request any.
    msg = aia_rag_user_message("CTX", "Q")
    assert "[N, #C" not in msg
    assert "keyword" not in msg.lower()
    assert "citation" not in msg.lower()


def test_user_message_enforces_table_discipline():
    # Small models otherwise append an empty hint column.
    msg = aia_rag_user_message("CTX", "Q").lower()
    assert "table reminder" in msg
    assert "hinweis" in msg or "note" in msg  # names the forbidden empty column


def test_user_message_has_no_language_specific_wordlist():
    # The instruction must not name a language.
    msg = aia_rag_user_message("CTX", "Q")
    # The user message must not pin the answer to one language.
    assert not re.search(r"answer in (german|english|french)", msg, re.IGNORECASE)
