"""Unit tests for exact-match post-hoc attribution.

A bare proper name embeds far from its surrounding prose (the same reason an author
can sit at fused rank ~59), so semantic attribution misses it. But the name is
LITERALLY in a chunk we already retrieved, whose page we already know — so we ground
the line by verbatim token presence against the in-context chunks first, and only fall
back to semantic search for reworded prose.

Pure functions: no DB, no LLM.
"""
from src.features.ai_assistant.routes._helpers import (
    _significant_tokens,
    _exact_attribution_chunk,
    _attribute_generic_text,
)


# ── _significant_tokens ──────────────────────────────────────────────────────

def test_significant_tokens_strips_markdown_and_filler():
    toks = _significant_tokens("- **Prof. Dr. Wolfgang Mauersberger**")
    assert "wolfgang" in toks and "mauersberger" in toks
    assert "dr" not in toks  # too short


def test_significant_tokens_drops_stopwords_keeps_content():
    toks = _significant_tokens("Die Autoren sind über die Quelle erreichbar")
    assert "die" not in toks and "sind" not in toks and "über" not in toks
    assert "autoren" in toks and "quelle" in toks and "erreichbar" in toks


def test_significant_tokens_keeps_email_as_one_token():
    toks = _significant_tokens("Kontakt: mmt-modul@medieninformatik-emden.de")
    assert "mmt-modul@medieninformatik-emden.de" in toks


# ── _exact_attribution_chunk ─────────────────────────────────────────────────

_CHUNKS = [
    {"source_id": 1, "page_number": 5, "content": "Einleitung und Überblick über das Thema."},
    {"source_id": 1, "page_number": 30, "content": "Autoren: Prof. Dr. Wolfgang Mauersberger und weitere."},
    {"source_id": 2, "page_number": 12, "content": "Kontakt unter mmt-modul@medieninformatik-emden.de erreichbar."},
]


def test_exact_match_finds_chunk_with_all_tokens():
    c = _exact_attribution_chunk("**Wolfgang Mauersberger**", _CHUNKS)
    assert c is not None and c["page_number"] == 30


def test_exact_match_finds_email_chunk():
    c = _exact_attribution_chunk("Erreichbar unter mmt-modul@medieninformatik-emden.de", _CHUNKS)
    assert c is not None and c["page_number"] == 12


def test_exact_match_none_when_not_all_tokens_present():
    # "Schneeberger" is not in any chunk -> no verbatim grounding
    assert _exact_attribution_chunk("**Heinrich Schneeberger**", _CHUNKS) is None


def test_exact_match_returns_first_in_order_for_duplicates():
    dups = [
        {"source_id": 7, "page_number": 100, "content": "Mauersberger steht hier."},
        {"source_id": 8, "page_number": 200, "content": "Mauersberger steht auch hier."},
    ]
    c = _exact_attribution_chunk("Mauersberger", dups)
    assert c["source_id"] == 7 and c["page_number"] == 100  # first (most relevant) wins


def test_exact_match_skips_toc_chunk():
    toc = [{"source_id": 1, "page_number": 2,
            "content": "Inhaltsverzeichnis\n1 Einleitung .... 5\n2 Mauersberger .... 30\n3 Schluss .... 60"}]
    # a table-of-contents lists terms verbatim but is never the real source
    assert _exact_attribution_chunk("Mauersberger", toc) is None


# ── _attribute_generic_text: exact match wins, no embedding needed ────────────

def test_attribute_uses_exact_match_without_search_hit():
    text = "- **Prof. Dr. Wolfgang Mauersberger**"
    out = _attribute_generic_text(
        text, lambda line: [], {1: 1},          # search_one returns NOTHING
        seen_pages_by_source={1: {5, 30}}, context_chunks=_CHUNKS,
    )
    assert "[1, S. 30]" in out  # grounded purely by verbatim presence


def test_attribute_exact_match_preferred_over_semantic():
    # semantic search points at page 99; exact match has the name on page 30 -> exact wins
    text = "- **Wolfgang Mauersberger**"
    semantic_hit = [{"source_id": 1, "page_number": 99, "content": "x", "vec_distance": 0.1}]
    out = _attribute_generic_text(
        text, lambda line: semantic_hit, {1: 1},
        seen_pages_by_source={1: {30, 99}}, context_chunks=_CHUNKS,
    )
    assert "[1, S. 30]" in out and "S. 99" not in out


def test_attribute_falls_back_to_semantic_for_reworded_prose():
    # a paraphrase whose tokens are NOT all verbatim in any chunk -> semantic path
    text = "Das Dokument behandelt grundlegende Konzepte ausführlich."
    semantic_hit = [{"source_id": 2, "page_number": 12, "content": "x", "vec_distance": 0.2}]
    out = _attribute_generic_text(
        text, lambda line: semantic_hit, {2: 3},
        seen_pages_by_source={2: {12}}, context_chunks=_CHUNKS,
    )
    assert "[3, S. 12]" in out
