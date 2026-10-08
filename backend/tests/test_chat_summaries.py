"""Greeting and overview read the source summaries, every other chat path stays untouched."""
from src.features.ai_assistant import summaries
from src.features.ai_assistant.routes import _greeting
from src.features.ai_assistant.routes._retrieval import _pack_context_batches
from src.features.ai_assistant.routes._source_map import build_source_pages


def _src(sid, summary):
    return {"id": sid, "filename": f"{sid}.pdf", "summary": summary}


def _first_page(monkeypatch, text="erste Seite"):
    monkeypatch.setattr(
        _greeting.db, "get_aia_chunks_by_source",
        lambda sid: [{"source_id": sid, "page_number": 1, "content": f"{text} {sid}"},
                     {"source_id": sid, "page_number": 2, "content": "zweite Seite"}],
    )


# --- summary_chunks -----------------------------------------------------------

def test_every_source_with_a_summary_becomes_one_chunk():
    out = summaries.summary_chunks([_src(1, "Über Alpha."), _src(2, "Über Beta.")])
    assert [(c["source_id"], c["content"]) for c in out] == [(1, "Über Alpha."), (2, "Über Beta.")]
    assert all(c["page_number"] is None and c["start_time"] is None for c in out)


def test_a_source_without_a_summary_yields_no_chunk():
    out = summaries.summary_chunks([_src(1, "Über Alpha."), _src(2, ""), _src(3, None)])
    assert [c["source_id"] for c in out] == [1]


def test_a_long_summary_is_capped():
    out = summaries.summary_chunks([_src(1, "x" * 10_000)])
    assert len(out[0]["content"]) == summaries.MAX_SUMMARY_CHARS


# --- greeting_chunks ----------------------------------------------------------

def test_greeting_takes_the_summary_where_there_is_one(monkeypatch):
    _first_page(monkeypatch)
    out = _greeting.greeting_chunks([1], {1: _src(1, "Über Alpha.")})
    assert [c["content"] for c in out] == ["Über Alpha."]


def test_greeting_falls_back_to_the_first_chunk_without_a_summary(monkeypatch):
    _first_page(monkeypatch)
    out = _greeting.greeting_chunks([1, 2], {1: _src(1, "Über Alpha."), 2: _src(2, "")})
    assert [c["content"] for c in out] == ["Über Alpha.", "erste Seite 2"]


def test_greeting_yields_nothing_when_no_source_has_a_summary(monkeypatch):
    # Then chat.py keeps the old way, fit shortcut or overview retrieval.
    _first_page(monkeypatch)
    assert _greeting.greeting_chunks([1, 2], {1: _src(1, ""), 2: _src(2, None)}) == []


def test_greeting_without_a_selection_yields_nothing():
    assert _greeting.greeting_chunks(None, {}) == []


# --- packing a chunk without a page --------------------------------------------

def test_pack_labels_a_summary_chunk_without_a_page():
    chunks = [{"source_id": 1, "page_number": None, "start_time": None, "content": "Über Alpha."}]
    batches, seen = _pack_context_batches(chunks, 10_000, {1: 1}, {1: {"filename": "a.pdf"}}, {})
    assert "<source>a.pdf | summary</source>" in batches[0]
    assert "S. None" not in batches[0]
    assert seen == {}


def test_source_pages_skip_a_chunk_without_a_spot():
    # A summary has no page to jump to, so it leaves no spot under the answer.
    chunks = [{"source_id": 1, "page_number": None, "start_time": None, "content": "Über Alpha."},
              {"source_id": 2, "page_number": None, "start_time": None, "content": "Über Beta."}]
    sources = {1: {"uuid": "u1", "filename": "a.pdf"}, 2: {"uuid": "u2", "filename": "b.pdf"}}
    out = build_source_pages(chunks, sources, umformen=False, umform_pages=[], popup_entry=None)
    assert out == []


# --- overview: the summaries stand in for the text ----------------------------

from src.features.ai_assistant.routes._greeting import overview_chunks


def _quelle(sid, summary):
    return {"id": sid, "summary": summary}


def test_ueberblick_nimmt_die_zusammenfassung_jeder_quelle():
    quellen = {1: _quelle(1, "Über Alpha."), 2: _quelle(2, "Über Beta.")}
    chunks = overview_chunks([1, 2], quellen)
    assert [c["content"] for c in chunks] == ["Über Alpha.", "Über Beta."]
    assert all(c["page_number"] is None for c in chunks)


def test_fehlt_eine_zusammenfassung_bleibt_der_alte_weg():
    """A source still being summarized would otherwise vanish from the overview."""
    quellen = {1: _quelle(1, "Über Alpha."), 2: _quelle(2, "")}
    assert overview_chunks([1, 2], quellen) == []


def test_ohne_gewaehlte_quellen_bleibt_der_alte_weg():
    assert overview_chunks(None, {}) == []
    assert overview_chunks([], {}) == []


def test_viele_zusammenfassungen_teilen_sich_das_budget():
    from src.features.ai_assistant.summaries import gekuerzt

    satz = "Das Gesetz regelt eine Sache. "
    chunks = [{"source_id": i, "page_number": None, "content": satz * 40} for i in range(4)]
    aus = gekuerzt(chunks, 400)
    assert len(aus) == 4
    assert all(len(c["content"]) <= 100 and c["content"].endswith(".") for c in aus)


def test_wenige_zusammenfassungen_bleiben_ganz():
    from src.features.ai_assistant.summaries import gekuerzt

    chunks = [{"source_id": 1, "page_number": None, "content": "Kurz und gut."}]
    assert gekuerzt(chunks, 60_000) == chunks
