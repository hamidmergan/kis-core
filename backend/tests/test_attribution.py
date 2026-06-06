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


# ── _attribution_chip (nav-only: page or timestamp, no offset/keyword) ───────

def test_attribution_chip_is_nav_only_pdf():
    assert _attribution_chip(2, _hit(1, 12, "x", 0.2), "line") == ["[2, S. 12]"]


def test_attribution_chip_is_nav_only_media():
    chunk = {"source_id": 3, "page_number": None, "content": "x", "vec_distance": 0.2, "start_time": 92.0}
    assert _attribution_chip(3, chunk, "line") == ["[3, 01:32]"]


# ── _attribute_generic_text (orchestration, injected search) ─────────────────

def _searcher(mapping):
    # mapping: line-substring -> hits
    def search_one(line):
        for key, hits in mapping.items():
            if key in line:
                return hits
        return []
    return search_one


def test_attributes_supported_line_nav_only():
    line = "Das Modul behandelt Audio Grafik und Video."
    search = _searcher({"Audio Grafik": [_hit(1, 12, "Audio Grafik und Video Kernmedien", 0.2)]})
    out = _attribute_generic_text(line, search, {1: 2}, max_distance=0.6)
    assert out == "Das Modul behandelt Audio Grafik und Video. [2, S. 12]"


def test_no_chip_when_unsupported():
    line = "Diese Aussage steht so nicht in den Quellen."
    search = _searcher({"Aussage": [_hit(1, 5, "irrelevant", 0.9)]})  # too far
    assert _attribute_generic_text(line, search, {1: 1}, max_distance=0.6) == line


def test_short_line_untouched():
    assert _attribute_generic_text("## Überblick", _searcher({}), {1: 1}) == "## Überblick"


def test_already_cited_line_untouched():
    line = "Fakt mit Quelle hier drin. [1, S. 3 | Fakt]"
    out = _attribute_generic_text(line, _searcher({"Fakt": [_hit(1, 9, "x", 0.1)]}), {1: 1})
    assert out == line


def test_unknown_source_qnum_no_chip():
    line = "Eine inhaltlich substanzielle Aussage zum Thema."
    search = _searcher({"substanzielle": [_hit(99, 5, "Aussage zum Thema", 0.2)]})
    # source_id 99 not in the qmap -> no chip
    assert _attribute_generic_text(line, search, {1: 1}, max_distance=0.6) == line


def test_offset_fn_positional_ignored():
    """offset_fn may still be passed as a positional arg (legacy caller) — must not crash."""
    line = "Das Modul behandelt Audio Grafik und Video."
    search = _searcher({"Audio Grafik": [_hit(1, 12, "Audio Grafik und Video Kernmedien", 0.2)]})
    dummy_offset_fn = lambda sid, page, ln: [" @5-30 | Audio Grafik und Video"]
    out = _attribute_generic_text(line, search, {1: 2}, dummy_offset_fn, max_distance=0.6)
    # offset_fn is ignored -> nav-only chip, NOT an offset chip
    assert out == "Das Modul behandelt Audio Grafik und Video. [2, S. 12]"


# ── cross-check: only chip when the source/page was actually retrieved ────────

def test_crosscheck_accepts_retrieved_page():
    line = "Eine inhaltlich substanzielle Aussage zum Thema hier."
    out = _attribute_generic_text(line, _searcher({"substanzielle": [_hit(1, 12, "x", 0.2)]}),
                                  {1: 2}, seen_pages_by_source={1: {12}}, max_distance=0.6)
    assert out == f"{line} [2, S. 12]"


def test_crosscheck_drops_unretrieved_page():
    line = "Eine inhaltlich substanzielle Aussage zum Thema hier."
    out = _attribute_generic_text(line, _searcher({"substanzielle": [_hit(1, 99, "x", 0.2)]}),
                                  {1: 2}, seen_pages_by_source={1: {12}}, max_distance=0.6)
    assert out == line


def test_crosscheck_media_passes_when_source_retrieved():
    line = "Eine inhaltlich substanzielle Aussage zum Thema hier."
    hit = {"source_id": 3, "page_number": None, "content": "x", "vec_distance": 0.2, "start_time": 92.0}
    out = _attribute_generic_text(line, _searcher({"substanzielle": [hit]}),
                                  {3: 1}, seen_pages_by_source={3: set()}, max_distance=0.6)
    assert out == f"{line} [1, 01:32]"


def test_no_crosscheck_when_not_passed():
    line = "Eine inhaltlich substanzielle Aussage zum Thema hier."
    out = _attribute_generic_text(line, _searcher({"substanzielle": [_hit(1, 7, "x", 0.2)]}),
                                  {1: 2}, max_distance=0.6)
    assert out == f"{line} [2, S. 7]"
