from src.features.ai_assistant.routes._helpers import resolve_citation_positions
from src.features.ai_assistant.routes._citation_match import Unit


class _Loader:
    def __init__(self, m): self._m = m
    def units(self, source, *, is_media): return self._m[source["id"]]


def test_media_uses_segment_not_chunk_start():
    text = "Kein Verzeichnis nötig. [2, 00:01 | kein Inhaltsverzeichnis]"
    units = {2: [
        Unit(None, 1.0, 16.0, "herzlich willkommen heute"),
        Unit(None, 179.0, 197.0, "was Sie weglassen kein Inhaltsverzeichnis Tabellenverzeichnis"),
    ]}
    src = {2: {"source": {"id": 2}, "is_media": True}}
    out = resolve_citation_positions(text, src, _Loader(units))
    assert "[2, 02:59 | kein Inhaltsverzeichnis]" in out  # 179s -> 02:59, not 00:01


def test_pdf_prefers_matched_page_over_typed():
    text = "Tools wie Zotero. [4, S. 13 | Literaturverwaltung Zotero Citavi]"
    units = {4: [
        Unit(13, None, None, "Literaturrecherche Überblick Schneeballprinzip"),
        Unit(15, None, None, "Umgang mit Literatur Literaturverwaltung Tools Zotero Citavi Mendeley"),
    ]}
    src = {4: {"source": {"id": 4}, "is_media": False}}
    out = resolve_citation_positions(text, src, _Loader(units))
    assert "[4, S. 15 |" in out  # not S. 13


def test_keeps_valid_model_time_when_no_keyword_hit():
    text = "Etwas Vages. [2, 05:00 | unauffindbares keyword xyz]"
    units = {2: [Unit(None, 1.0, 600.0, "ganz anderer text")]}  # chunk spans 0-600
    src = {2: {"source": {"id": 2}, "is_media": True}}
    out = resolve_citation_positions(text, src, _Loader(units))
    assert "[2, 05:00 |" in out  # 300s is inside [1,600], model time kept
