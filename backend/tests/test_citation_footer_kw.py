from src.features.ai_assistant.routes._helpers import resolve_citation_positions, SourceUnitLoader


def _pages(monkeypatch, chunks):
    monkeypatch.setattr(
        "src.features.ai_assistant.repository.chunks.get_aia_chunks_by_source",
        lambda sid: chunks)


def test_drops_model_footer_keyword_keeps_page(monkeypatch):
    # footer ("06.05.2026" + "Wiss Seminar Kleinau") repeats on every page -> furniture
    chunks = [{"page_number": p, "start_time": None,
               "content": f"06.05.2026\nWiss Seminar Kleinau\n{p}\nBody seite {p} inhalt"} for p in (2, 3, 5)]
    _pages(monkeypatch, chunks)
    sources = {5: {"source": {"id": 9}, "is_media": False, "pages": {2, 3, 5}}}
    out = resolve_citation_positions("Umfang. [5, S. 3 | 06.05.2026 Wiss Seminar Kleinau]", sources, SourceUnitLoader())
    assert "[5, S. 3]" in out          # page kept, footer keyword dropped (position-only chip)
    assert "06.05.2026" not in out     # footer text no longer anywhere in the citation


def test_keeps_real_body_keyword(monkeypatch):
    chunks = [{"page_number": p, "start_time": None,
               "content": f"06.05.2026\nWiss Seminar Kleinau\n{p}\nBody seite {p} Spezialinhalt{p}"} for p in (2, 3)]
    _pages(monkeypatch, chunks)
    sources = {5: {"source": {"id": 9}, "is_media": False, "pages": {2, 3}}}
    out = resolve_citation_positions("X. [5, S. 3 | Spezialinhalt3]", sources, SourceUnitLoader())
    assert "Spezialinhalt3" in out      # genuine body keyword preserved
