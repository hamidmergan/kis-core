"""Tests for page-scoped retrieval: when a question names an explicit page
("fasse Seite 5 zusammen", "summarize page 12"), the chat route pulls exactly
that page's chunks as context instead of running semantic hybrid search where the
page number is just another search token.

Two units:
  * ``_parse_page_refs``  – pure, language-agnostic-ish extraction of page numbers
    (German "Seite"/"S.", English "page"/"p.", ranges) from the raw question.
  * ``_retrieve_page_scoped_context`` – loads a source's chunks (db) and keeps only
    those on the requested pages.

db is monkeypatched so these stay deterministic and offline.
"""
from src.features.ai_assistant.routes import chat as chat_mod
from src.features.ai_assistant.routes.chat import (
    _parse_page_refs,
    _retrieve_page_scoped_context,
    _scope_unfulfillable_message,
)


# ── _parse_page_refs ─────────────────────────────────────────────────────────

def test_parses_german_seite():
    assert _parse_page_refs("fasse Seite 5 zusammen") == [5]


def test_parses_german_abbreviation():
    assert _parse_page_refs("was steht auf S. 5?") == [5]


def test_parses_english_page():
    assert _parse_page_refs("summarize page 12") == [12]


def test_parses_english_abbreviation():
    assert _parse_page_refs("see p. 12 for details") == [12]


def test_expands_range():
    assert _parse_page_refs("fasse Seite 5-7 zusammen") == [5, 6, 7]


def test_expands_range_with_bis():
    assert _parse_page_refs("Seiten 5 bis 7") == [5, 6, 7]


def test_reversed_range_is_normalised():
    assert _parse_page_refs("Seite 7-5") == [5, 6, 7]


def test_multiple_pages_deduplicated_and_sorted():
    assert _parse_page_refs("vergleiche Seite 9 und Seite 3") == [3, 9]


def test_no_page_keyword_returns_empty():
    # A bare number without a page keyword must NOT trigger page scoping.
    assert _parse_page_refs("fasse die 5 wichtigsten Punkte zusammen") == []


def test_no_number_returns_empty():
    assert _parse_page_refs("worum geht es in dem Dokument?") == []


def test_webseite_does_not_match_seite():
    # Word boundary: "Webseite" must not be read as "Seite".
    assert _parse_page_refs("die Webseite 5 ist down") == []


def test_absurd_span_collapses_to_start():
    # Guard against "page 1-9999" pulling the whole document.
    assert _parse_page_refs("Seiten 1-9999") == [1]


# ── tolerant range separators (typos / glued tokens) ─────────────────────────

def test_hyphen_glued_to_bis():
    # The reported bug: "Seite 12 -bis 14" (a stray hyphen before "bis").
    assert _parse_page_refs("fasse Seite 12 -bis 14 zusammen") == [12, 13, 14]


def test_bis_glued_to_hyphen():
    assert _parse_page_refs("Seite 12 bis-14") == [12, 13, 14]


def test_em_dash_range():
    assert _parse_page_refs("Seite 12—14") == [12, 13, 14]


def test_spaced_hyphen_range():
    assert _parse_page_refs("Seite 12 - 14") == [12, 13, 14]


def test_hyphen_bis_hyphen():
    assert _parse_page_refs("Seite 12 - bis - 14") == [12, 13, 14]


def test_keyword_glued_to_number():
    # "things written together": no space between keyword and number.
    assert _parse_page_refs("fasse Seite12 zusammen") == [12]


def test_bare_space_is_not_a_range():
    # "Seite 12 14" must NOT be read as a range (no connector token).
    assert _parse_page_refs("Seite 12 14") == [12]


# ── _retrieve_page_scoped_context ────────────────────────────────────────────

def _chunk(sid, page, content="x"):
    return {"id": page, "source_id": sid, "page_number": page, "content": content}


def test_keeps_only_requested_pages(monkeypatch):
    chunks = [_chunk(1, 4), _chunk(1, 5), _chunk(1, 5, "b"), _chunk(1, 6)]
    monkeypatch.setattr(chat_mod.db, "get_aia_chunks_by_source", lambda sid: chunks)
    out = _retrieve_page_scoped_context([1], [5])
    assert [c["page_number"] for c in out] == [5, 5]


def test_spans_multiple_sources(monkeypatch):
    by_source = {
        1: [_chunk(1, 5), _chunk(1, 6)],
        2: [_chunk(2, 5), _chunk(2, 7)],
    }
    monkeypatch.setattr(chat_mod.db, "get_aia_chunks_by_source", lambda sid: by_source[sid])
    out = _retrieve_page_scoped_context([1, 2], [5])
    assert {(c["source_id"], c["page_number"]) for c in out} == {(1, 5), (2, 5)}


def test_missing_page_returns_empty(monkeypatch):
    monkeypatch.setattr(chat_mod.db, "get_aia_chunks_by_source", lambda sid: [_chunk(1, 4)])
    assert _retrieve_page_scoped_context([1], [99]) == []


# ── _scope_unfulfillable_message (generic can't-help for unservable scope asks) ─
# A page/time scope was explicitly requested but cannot be served (absent / wrong
# source kind). We return a GENERIC can't-help message — distinct from the genuine
# "no info in sources" content sentinel, which must stay for real topic gaps.

def test_unfulfillable_when_scope_requested_but_no_chunks():
    assert _scope_unfulfillable_message(True, None, "de") is not None
    assert _scope_unfulfillable_message(True, [], "de") is not None


def test_localised_message():
    de = _scope_unfulfillable_message(True, None, "de")
    en = _scope_unfulfillable_message(True, None, "en")
    assert de != en
    assert de and en


def test_unknown_locale_falls_back_to_german():
    assert _scope_unfulfillable_message(True, None, "fr") == _scope_unfulfillable_message(True, None, "de")


def test_none_when_scope_request_fulfilled():
    # Chunks present -> the scope was served -> no can't-help message.
    assert _scope_unfulfillable_message(True, [{"page_number": 5}], "de") is None


def test_none_when_no_scope_requested():
    # Not a scope question at all -> never short-circuit (normal RAG, incl. the real
    # "no info in sources" sentinel, stays in charge).
    assert _scope_unfulfillable_message(False, None, "de") is None
