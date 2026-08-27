"""Three limits against a runaway chat question: schema, search query, budget."""
import pytest
from pydantic import ValidationError

from src.limits import AIA_QUESTION_MAX_CHARS, AIA_EMBED_QUERY_MAX_CHARS
from src.features.ai_assistant.schemas import ChatBody
from src.features.ai_assistant.routes.chat import (
    _truncate_query_for_embedding,
    _reserve_question_budget,
)


# ── 1. Schema cap (ChatBody.question) ───────────────────────────────────────

def test_schema_accepts_normal_question():
    body = ChatBody(question="Was steht in Paragraph 3?")
    assert body.question == "Was steht in Paragraph 3?"


def test_schema_accepts_question_at_exact_limit():
    body = ChatBody(question="x" * AIA_QUESTION_MAX_CHARS)
    assert len(body.question) == AIA_QUESTION_MAX_CHARS


def test_schema_rejects_question_over_limit():
    with pytest.raises(ValidationError):
        ChatBody(question="x" * (AIA_QUESTION_MAX_CHARS + 1))


def test_schema_rejects_empty_question():
    with pytest.raises(ValidationError):
        ChatBody(question="")


# ── 2. Retrieval-query truncation (_truncate_query_for_embedding) ───────────

def test_short_query_is_unchanged():
    q = "Wer sind die Autoren?"
    assert _truncate_query_for_embedding(q) == q


def test_long_query_is_truncated_to_embed_cap():
    long_q = "wort " * 5000  # ~25k chars, well over the embed cap
    out = _truncate_query_for_embedding(long_q)
    assert len(out) == AIA_EMBED_QUERY_MAX_CHARS
    assert long_q.startswith(out)  # a prefix, not a reshuffle


def test_query_at_exact_embed_cap_is_unchanged():
    q = "y" * AIA_EMBED_QUERY_MAX_CHARS
    assert _truncate_query_for_embedding(q) == q


def test_empty_query_is_returned_as_is():
    assert _truncate_query_for_embedding("") == ""


def test_embed_cap_is_below_schema_cap():
    # The embedding limit has to be tighter, otherwise nothing is ever shortened.
    assert AIA_EMBED_QUERY_MAX_CHARS < AIA_QUESTION_MAX_CHARS


# ── 3. Context-budget reservation (_reserve_question_budget) ────────────────

def test_budget_reserves_question_length_plus_overhead():
    budget = 250_000
    question = "x" * 8000
    out = _reserve_question_budget(budget, question)
    assert out == budget - 8000 - 200


def test_budget_floors_at_1000_for_tiny_budget():
    # Even with a tiny budget usable context remains.
    out = _reserve_question_budget(1500, "x" * AIA_QUESTION_MAX_CHARS)
    assert out == 1000


def test_budget_handles_empty_question():
    assert _reserve_question_budget(250_000, "") == 250_000 - 200


def test_budget_reservation_is_negligible_for_normal_question():
    # A normal short question barely dents a large budget.
    budget = 250_000
    out = _reserve_question_budget(budget, "Was steht auf Seite 5?")
    assert budget - out < 300
