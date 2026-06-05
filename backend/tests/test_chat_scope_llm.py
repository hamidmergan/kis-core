"""LLM-based scope extraction (Self-Query Retrieval): the model turns ANY phrasing
("fasse alles zwischen 12 und 13 zusammen", "was wird bei Minute 10 erzählt",
"ab 10 min") into a structured page/time scope, so retrieval is no longer at the
mercy of a hand-written regex. These cover the PURE pieces (JSON parsing, interval
expansion, time conversion, media retrieval); the LLM call itself is thin glue.
"""
from src.features.ai_assistant.routes import chat as chat_mod
from src.features.ai_assistant.routes.chat import (
    _parse_scope_response,
    _expand_page_intervals,
    _page_scope_too_large,
    _time_intervals_to_seconds,
    _retrieve_time_scoped_context,
    _first_source_kind,
)


# ── _parse_scope_response (tolerant JSON) ────────────────────────────────────

def test_parses_plain_json():
    assert _parse_scope_response('{"unit":"page","intervals":[[12,13]]}') == {
        "unit": "page", "intervals": [[12, 13]]}


def test_parses_json_in_code_fence():
    raw = '```json\n{"unit":"time","intervals":[[10,10]]}\n```'
    assert _parse_scope_response(raw) == {"unit": "time", "intervals": [[10, 10]]}


def test_parses_json_with_surrounding_prose():
    raw = 'Sure, here you go: {"unit":"page","intervals":[[5,5],[10,10]]} done.'
    assert _parse_scope_response(raw) == {"unit": "page", "intervals": [[5, 5], [10, 10]]}


def test_strips_think_block():
    raw = '<think>the user wants pages</think>{"unit":"page","intervals":[[1,2]]}'
    assert _parse_scope_response(raw) == {"unit": "page", "intervals": [[1, 2]]}


def test_keeps_open_ended_null():
    assert _parse_scope_response('{"unit":"page","intervals":[[10,null]]}') == {
        "unit": "page", "intervals": [[10, None]]}


def test_garbage_returns_empty():
    assert _parse_scope_response("no json here") == {"unit": None, "intervals": []}
    assert _parse_scope_response("") == {"unit": None, "intervals": []}


def test_drops_malformed_intervals_and_unit():
    raw = '{"unit":"weird","intervals":[[1,2],[3],"x",[4,5]]}'
    assert _parse_scope_response(raw) == {"unit": None, "intervals": [[1, 2], [4, 5]]}


# ── _expand_page_intervals ───────────────────────────────────────────────────

def test_expands_range():
    assert _expand_page_intervals([[12, 14]], max_page=100) == [12, 13, 14]


def test_expands_discrete_points():
    assert _expand_page_intervals([[5, 5], [10, 10]], max_page=100) == [5, 10]


def test_open_ended_uses_max_page():
    assert _expand_page_intervals([[10, None]], max_page=12) == [10, 11, 12]


def test_reversed_interval_normalised():
    assert _expand_page_intervals([[14, 12]], max_page=100) == [12, 13, 14]


def test_absurd_span_collapses():
    assert _expand_page_intervals([[1, 9999]], max_page=10000) == [1]


# ── _page_scope_too_large (whole-doc range -> route to GENERIC) ───────────────

def test_huge_range_is_too_large():
    # "fasse Seite 1 bis 450" — summarizing the whole document is an overview, not a
    # precise scope; route it to GENERIC instead of scoping/collapsing.
    assert _page_scope_too_large([[1, 450]], max_page=450, limit=50) is True


def test_small_range_is_not_too_large():
    assert _page_scope_too_large([[12, 15]], max_page=450, limit=50) is False


def test_open_ended_over_long_doc_is_too_large():
    # "ab Seite 10" on a 450-page doc -> 441 pages -> overview.
    assert _page_scope_too_large([[10, None]], max_page=450, limit=50) is True


def test_open_ended_over_short_doc_is_not_too_large():
    assert _page_scope_too_large([[10, None]], max_page=30, limit=50) is False


def test_discrete_points_not_too_large():
    assert _page_scope_too_large([[5, 5], [10, 10]], max_page=100, limit=50) is False


# ── _time_intervals_to_seconds (minutes → seconds) ───────────────────────────

def test_point_minute_to_second_window():
    # "Minute 10" -> the whole 10th minute: 600s up to (but not incl.) 660s.
    assert _time_intervals_to_seconds([[10, 10]], max_seconds=3600) == [(600, 660)]


def test_minute_range_to_seconds():
    # "between 10 and 12 min" -> 10:00 through end of minute 12.
    assert _time_intervals_to_seconds([[10, 12]], max_seconds=3600) == [(600, 780)]


def test_open_ended_time_uses_max_seconds():
    assert _time_intervals_to_seconds([[10, None]], max_seconds=1500) == [(600, 1500)]


# ── _retrieve_time_scoped_context ────────────────────────────────────────────

def _mchunk(sid, start, end, content="x"):
    return {"id": start, "source_id": sid, "page_number": None,
            "start_time": start, "end_time": end, "content": content}


def test_keeps_chunks_overlapping_range(monkeypatch):
    chunks = [_mchunk(1, 0, 300), _mchunk(1, 300, 600), _mchunk(1, 595, 605), _mchunk(1, 660, 900)]
    monkeypatch.setattr(chat_mod.db, "get_aia_chunks_by_source", lambda sid: chunks)
    # window [600,660): only the chunk spanning 595-605 overlaps.
    out = _retrieve_time_scoped_context(1, [(600, 660)])
    assert [(c["start_time"], c["end_time"]) for c in out] == [(595, 605)]


def test_skips_non_media_chunks(monkeypatch):
    chunks = [{"id": 1, "source_id": 1, "start_time": None, "end_time": None, "content": "pdf"}]
    monkeypatch.setattr(chat_mod.db, "get_aia_chunks_by_source", lambda sid: chunks)
    assert _retrieve_time_scoped_context(1, [(0, 600)]) == []


# ── _first_source_kind ───────────────────────────────────────────────────────

def _sources(*items):
    return {i: {"id": i, "filename": fn} for i, fn in items}


def test_first_source_pdf():
    assert _first_source_kind([7, 8], _sources((7, "a.pdf"), (8, "b.mp4"))) == "pdf"


def test_first_source_media():
    assert _first_source_kind([7], _sources((7, "lecture.mp4"))) == "media"
    assert _first_source_kind([7], _sources((7, "talk.mp3"))) == "media"


def test_first_source_unknown_kind():
    assert _first_source_kind([7], _sources((7, "notes.txt"))) is None
    assert _first_source_kind(None, {}) is None
    assert _first_source_kind([], {}) is None
