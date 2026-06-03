import src.features.ai_assistant.repository.chunks as chunk_repo
from src.features.ai_assistant.routes._helpers import SourceUnitLoader


def _chunks():
    return [
        {"page_number": 32, "content": "Alesis Digital Audio Tape ADT im Fliesstext"},
        {"page_number": 440, "content": "ADAT Alesis Digital Audio Tape Verzeichnis"},
        {"page_number": 441, "content": "weitere Verzeichniseintraege hier"},
    ]


def test_loader_restricts_to_seen_pages(monkeypatch):
    # Only the pages the model actually saw (440, 441) survive; the body page 32 — which
    # the model never saw — is dropped, so a claim can't be grounded to an unseen page.
    monkeypatch.setattr(chunk_repo, "get_aia_chunks_by_source", lambda sid: _chunks())
    loader = SourceUnitLoader(seen_pages_by_source={7: {440, 441}})
    units = loader.units({"id": 7}, is_media=False)
    assert {u.page for u in units} == {440, 441}


def test_loader_without_seen_pages_keeps_all(monkeypatch):
    # No seen-page set -> backward compatible: every page is a candidate.
    monkeypatch.setattr(chunk_repo, "get_aia_chunks_by_source", lambda sid: _chunks())
    loader = SourceUnitLoader()
    units = loader.units({"id": 7}, is_media=False)
    assert {u.page for u in units} == {32, 440, 441}


def test_loader_empty_seen_set_for_source_keeps_all(monkeypatch):
    # A source missing from the map (or with an empty set) must NOT be filtered to
    # nothing — absence of seen data means "don't restrict", never "drop everything".
    monkeypatch.setattr(chunk_repo, "get_aia_chunks_by_source", lambda sid: _chunks())
    loader = SourceUnitLoader(seen_pages_by_source={99: {1}})  # different source id
    units = loader.units({"id": 7}, is_media=False)
    assert {u.page for u in units} == {32, 440, 441}
