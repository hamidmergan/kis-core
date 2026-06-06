"""Post-hoc semantic attribution for GENERIC answers.

Instead of trusting the model's (often wrong) page citations in an overview answer,
we re-ground EACH answer line with the same semantic search that works perfectly for
specific questions: embed the line, search the active sources, and attach the best
chunk's citation — BUT only when it is close enough (distance gate). A line that is
not clearly supported gets NO chip (no fabricated attribution / post-rationalization).
"""
from src.features.ai_assistant.routes._helpers import (
    _pick_attribution,
    _attribution_chip,
    _attribute_generic_text,
)


def _hit(sid, page, content, dist, start=None):
    return {"source_id": sid, "page_number": page, "content": content,
            "vec_distance": dist, "start_time": start}


# ── _pick_attribution (distance gate) ────────────────────────────────────────

def test_picks_closest_within_gate():
    hits = [_hit(1, 5, "a", 0.45), _hit(1, 7, "b", 0.20)]
    assert _pick_attribution(hits, 0.6)["page_number"] == 7  # closest wins


def test_rejects_when_all_too_far():
    hits = [_hit(1, 5, "a", 0.80), _hit(1, 7, "b", 0.75)]
    assert _pick_attribution(hits, 0.6) is None


def test_empty_hits_returns_none():
    assert _pick_attribution([], 0.6) is None


def test_ignores_hits_without_distance():
    assert _pick_attribution([{"source_id": 1, "page_number": 5}], 0.6) is None


# ── _attribution_chip (server offsets preferred -> tight highlight) ───────────

def _no_offsets(*_a):
    return []


def _offsets(suffixes):
    def fn(_sid, _page, _line):
        return suffixes
    return fn


def test_pdf_chip_uses_server_offsets():
    chunk = _hit(1, 12, "content", 0.2)
    chips = _attribution_chip(2, chunk, "line", _offsets([" @10-40 | technische Grundlagen"]))
    assert chips == ["[2, S. 12 @10-40 | technische Grundlagen]"]  # exact span, no paragraph expansion


def test_pdf_chip_multiple_offset_regions():
    chunk = _hit(1, 12, "content", 0.2)
    chips = _attribution_chip(1, chunk, "line", _offsets([" @10-40 | A", " @60-90 | B"]))
    assert chips == ["[1, S. 12 @10-40 | A]", "[1, S. 12 @60-90 | B]"]


def test_pdf_chip_keyword_fallback_when_no_offsets():
    chunk = _hit(1, 12, "Das Modul behandelt Audio Grafik und Video als Kernmedien", 0.2)
    chips = _attribution_chip(2, chunk, "Im Modul sind Audio Grafik und Video zentral.", _no_offsets)
    assert chips == ["[2, S. 12 | Audio Grafik und Video]"]


def test_pdf_chip_nav_only_when_no_offset_no_overlap():
    chunk = _hit(1, 9, "voellig anderer wortschatz hier", 0.2)
    assert _attribution_chip(1, chunk, "Komplett andere Aussage ohne Bezug.", _no_offsets) == ["[1, S. 9]"]


def test_media_chip_uses_timestamp():
    chunk = {"source_id": 3, "page_number": None, "content": "x", "vec_distance": 0.2, "start_time": 92.0}
    assert _attribution_chip(3, chunk, "irgendeine Zeile", _no_offsets) == ["[3, 01:32]"]


# ── _attribute_generic_text (orchestration, injected search) ─────────────────

def _searcher(mapping):
    # mapping: line-substring -> hits
    def search_one(line):
        for key, hits in mapping.items():
            if key in line:
                return hits
        return []
    return search_one


def test_attributes_supported_line_with_offsets():
    line = "Das Modul behandelt Audio Grafik und Video."
    search = _searcher({"Audio Grafik": [_hit(1, 12, "Audio Grafik und Video Kernmedien", 0.2)]})
    out = _attribute_generic_text(line, search, {1: 2}, _offsets([" @5-30 | Audio Grafik und Video"]), max_distance=0.6)
    assert out == "Das Modul behandelt Audio Grafik und Video. [2, S. 12 @5-30 | Audio Grafik und Video]"


def test_no_chip_when_unsupported():
    line = "Diese Aussage steht so nicht in den Quellen."
    search = _searcher({"Aussage": [_hit(1, 5, "irrelevant", 0.9)]})  # too far
    assert _attribute_generic_text(line, search, {1: 1}, _no_offsets, max_distance=0.6) == line


def test_short_line_untouched():
    assert _attribute_generic_text("## Überblick", _searcher({}), {1: 1}, _no_offsets) == "## Überblick"


def test_already_cited_line_untouched():
    line = "Fakt mit Quelle hier drin. [1, S. 3 | Fakt]"
    out = _attribute_generic_text(line, _searcher({"Fakt": [_hit(1, 9, "x", 0.1)]}), {1: 1}, _no_offsets)
    assert out == line


def test_unknown_source_qnum_no_chip():
    line = "Eine inhaltlich substanzielle Aussage zum Thema."
    search = _searcher({"substanzielle": [_hit(99, 5, "Aussage zum Thema", 0.2)]})
    # source_id 99 not in the qmap -> no chip
    assert _attribute_generic_text(line, search, {1: 1}, _no_offsets, max_distance=0.6) == line
