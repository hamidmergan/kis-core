"""With an explicit reference citations may only come from the reference window."""
from src.features.ai_assistant.routes._evidence import _attribute_generic_text, _scope_chunk_ids


def _hit(sid, page, content, dist, start=None, cid=None):
    return {"id": cid, "source_id": sid, "page_number": page, "content": content,
            "vec_distance": dist, "start_time": start}


def _media_chunk(cid, start):
    # A media chunk carries a timestamp and a segment number, no page.
    return {"id": cid, "source_id": 3, "page_number": cid, "content": "x",
            "start_time": start, "end_time": start + 30}


# ── _scope_chunk_ids ─────────────────────────────────────────────────────────

def test_scope_ids_none_for_no_scope():
    assert _scope_chunk_ids(None) is None
    assert _scope_chunk_ids([]) is None


def test_scope_ids_collects_chunk_ids():
    assert _scope_chunk_ids([{"id": 10}, {"id": 11}]) == {10, 11}


def test_scope_ids_none_when_chunks_lack_ids():
    # Defensive: never restrict to an empty set (that would nuke every chip).
    assert _scope_chunk_ids([{"source_id": 1}]) is None


# ── attribution is clamped to the scoped window ──────────────────────────────

def _searcher(hits):
    return lambda line: hits


def test_scoped_media_cites_inside_window_not_the_closer_outside_hit():
    line = "Quellenarten umfassen physische Zeitschriften und digitale Bibliotheken."
    # Out-of-scope hit (13:06) is SEMANTICALLY CLOSER than the in-scope one (41:00).
    out_hit = _hit(3, 13, "frühe Passage", 0.10, start=786.0, cid=13)
    in_hit = _hit(3, 41, "späte Passage", 0.30, start=2460.0, cid=101)
    scope = [_media_chunk(101, 2460.0)]
    out = _attribute_generic_text(
        line, _searcher([out_hit, in_hit]), {3: 1},
        seen_pages_by_source={3: set()},  # media: source-level seen-set (empty)
        scope_chunks=scope,
    )
    assert "[1, 41:00]" in out      # the chip the model actually saw
    assert "13:06" not in out       # the leak must be gone


def test_scoped_media_drops_chip_when_only_outside_hit_matches():
    line = "Vor Beginn der Recherche sollte eine grobe Eingrenzung erfolgen."
    out_hit = _hit(3, 13, "frühe Passage", 0.10, start=786.0, cid=13)
    scope = [_media_chunk(101, 2460.0)]
    out = _attribute_generic_text(
        line, _searcher([out_hit]), {3: 1},
        seen_pages_by_source={3: set()},
        scope_chunks=scope,
    )
    assert out == line              # no in-scope support → no (wrong) chip


def test_no_scope_keeps_closest_hit_unchanged():
    # Without a reference the existing behaviour stays.
    line = "Quellenarten umfassen physische Zeitschriften und digitale Bibliotheken."
    out_hit = _hit(3, 13, "frühe Passage", 0.10, start=786.0, cid=13)
    in_hit = _hit(3, 41, "späte Passage", 0.30, start=2460.0, cid=101)
    out = _attribute_generic_text(
        line, _searcher([out_hit, in_hit]), {3: 1},
        seen_pages_by_source={3: set()},
        scope_chunks=None,
    )
    assert "[1, 13:06]" in out


def test_scoped_pdf_multipage_cites_inside_window():
    # The same bracket also protects a multi-page PDF reference.
    line = "Die Filterung im Frequenzbereich nutzt die diskrete Fouriertransformation."
    out_hit = _hit(1, 30, "andere Seite", 0.10, cid=30)
    in_hit = _hit(1, 13, "Seite im Scope", 0.30, cid=113)
    scope = [{"id": 113, "source_id": 1, "page_number": 13, "start_time": None}]
    out = _attribute_generic_text(
        line, _searcher([out_hit, in_hit]), {1: 1},
        seen_pages_by_source={1: {13}},
        scope_chunks=scope,
    )
    assert "[1, S. 13]" in out
    assert "S. 30" not in out
