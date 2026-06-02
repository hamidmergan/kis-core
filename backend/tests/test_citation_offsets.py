"""Architecture B: exact offset-span anchoring for PDF citation highlights."""
import pytest

from src.features.ai_assistant.routes._page_geometry import (
    locate_claim_span,
    span_text,
    offset_suffix,
)
from src.features.ai_assistant.routes._helpers import (
    resolve_citation_positions,
    fill_uncited_lines,
    _CITE_RESOLVE_RE,
    _HAS_CITE,
)
from src.features.ai_assistant.routes._citation_match import Unit


# ── locate_claim_span ─────────────────────────────────────────────────────────

def test_locate_span_expands_paraphrase_to_full_sentence():
    page = ("Ist die Frage so formuliert, dass sie eine gute Antwort ermoeglicht? "
            "Passt die Fragestellung zum Thema? Manchmal driftet man ab.")
    # Model paraphrase shares only "Passt die ... zum Thema" verbatim.
    span = locate_claim_span(page, "Passt die Frage zum Thema?")
    assert span is not None
    start, end = span
    assert page[start:end + 1] == "Passt die Fragestellung zum Thema?"


def test_locate_span_returns_none_for_unrelated_claim():
    page = "Kapitel 10 Wahrscheinlichkeitsrechnung Zufall Varianz Erwartungswert."
    assert locate_claim_span(page, "voellig anderes thema ohne jeden bezug") is None


def test_locate_span_does_not_split_on_abbreviation_dot():
    page = "Tools wie z.B. Zotero und Citavi helfen bei der Literaturverwaltung heute."
    span = locate_claim_span(page, "Literaturverwaltung mit Zotero und Citavi")
    assert span is not None
    start, end = span
    # The 'z.B.' dot must NOT end the sentence — the span keeps the whole line.
    assert "z.B." in page[start:end + 1]
    assert page[start:end + 1].endswith("heute.")


def test_locate_span_is_diacritic_insensitive():
    # PDF text layer kept the umlaut; the claim lost it (LaTeX/maths PDFs).
    page = "Die Dezimalbrueche werden hier ausfuehrlich erklaert und geuebt."
    span = locate_claim_span(page, "Erklaerung der Dezimalbrueche")
    assert span is not None


def test_locate_span_caps_runaway_sentence():
    page = "Anfang " + "wort " * 200 + "ende der langen passage."
    span = locate_claim_span(page, "wort wort wort")
    assert span is not None
    start, end = span
    assert end - start + 1 <= 220


# ── span_text ─────────────────────────────────────────────────────────────────

def test_span_text_collapses_whitespace_and_strips_chip_chars():
    page = "Erste   Zeile\nmit [Klammern] und | Pipe darin."
    txt = span_text(page, 0, len(page) - 1)
    assert "\n" not in txt and "  " not in txt
    assert "[" not in txt and "]" not in txt and "|" not in txt
    assert "Klammern" in txt  # the visible cell text survives


# ── offset_suffix (page-text I/O monkeypatched) ───────────────────────────────

def test_offset_suffix_builds_at_marker(monkeypatch):
    import src.features.ai_assistant.routes._page_geometry as g
    page = "Vorwort hier. Passt die Fragestellung zum Thema? Schluss."
    monkeypatch.setattr(g, "get_page_text", lambda *a, **k: page)
    suf = offset_suffix({"id": 1, "file_type": "pdf"}, 8, "Passt die Frage zum Thema?")
    assert suf is not None
    assert suf.startswith(" @") and " | " in suf
    assert "Passt die Fragestellung zum Thema?" in suf


def test_offset_suffix_none_when_no_page_text(monkeypatch):
    import src.features.ai_assistant.routes._page_geometry as g
    monkeypatch.setattr(g, "get_page_text", lambda *a, **k: None)
    assert offset_suffix({"id": 1, "file_type": "pdf"}, 8, "irgendetwas") is None


# ── chip round-trips through the strip/detect regexes ─────────────────────────

def test_offset_chip_is_stripped_by_cite_regex():
    stripped = _CITE_RESOLVE_RE.sub("", "Foo [1, S. 8 @12-47 | ein Satz] bar")
    assert "[" not in stripped and "@" not in stripped
    assert "Foo" in stripped and "bar" in stripped


def test_offset_table_chip_detected_as_already_cited():
    assert _HAS_CITE.search("| Abgabe | 03.07. [4, S. 6 @1-20 ❘ Abgabe Termin] |".rstrip())


# ── resolver / fill wiring (fake loader with offset_suffix) ───────────────────

class _OffLoader:
    """Fake loader that exposes ``offset_suffix`` like the real SourceUnitLoader,
    resolving offsets against an in-memory page-text map (no file I/O)."""
    def __init__(self, units, pages):
        self._u = units
        self._pages = pages

    def units(self, source, *, is_media):
        return self._u[source["id"]]

    def offset_suffix(self, source, page_number, claim):
        T = self._pages.get((source["id"], page_number))
        if not T:
            return None
        span = locate_claim_span(T, claim)
        if not span:
            return None
        s, e = span
        return f" @{s}-{e} | {span_text(T, s, e)}"


def test_resolve_emits_offset_anchor_for_pdf():
    text = "Passt die Frage zum Thema? [5, S. 8 | Passt die Fragestellung]"
    units = {5: [Unit(8, None, None, "Passt die Fragestellung zum Thema Manchmal driftet man ab")]}
    pages = {(5, 8): "Leitfrage. Passt die Fragestellung zum Thema? Manchmal driftet man ab."}
    src = {5: {"source": {"id": 5, "file_type": "pdf"}, "is_media": False, "pages": {8}}}
    out = resolve_citation_positions(text, src, _OffLoader(units, pages))
    assert "[5, S. 8 @" in out                       # offset marker present
    assert "Passt die Fragestellung zum Thema?" in out  # exact verbatim span carried


def test_resolve_keeps_keyword_chip_when_no_page_text():
    text = "Etwas. [5, S. 8 | Passt die Fragestellung]"
    units = {5: [Unit(8, None, None, "Passt die Fragestellung zum Thema")]}
    src = {5: {"source": {"id": 5, "file_type": "pdf"}, "is_media": False, "pages": {8}}}
    out = resolve_citation_positions(text, src, _OffLoader(units, pages={}))  # no page text
    assert "@" not in out
    assert "[5, S. 8 | Passt die Fragestellung]" in out


def test_fill_emits_offset_anchor_for_pdf():
    text = "- Passt die Frage zum Thema?\n"
    units = [Unit(page=8, start_time=None, end_time=None,
                  raw_text="Passt die Fragestellung zum Thema Manchmal driftet man ab")]
    pages = {(2, 8): "Vorwort. Passt die Fragestellung zum Thema? Schluss hier."}
    sources = {2: {"source": {"id": 2, "file_type": "pdf"}, "is_media": False}}
    out = fill_uncited_lines(text, sources, _OffLoader({2: units}, pages))
    assert "[2, S. 8 @" in out
    assert "Passt die Fragestellung zum Thema?" in out


def test_fill_table_row_uses_non_pipe_separator_with_offsets():
    text = "| Abgabe Hausarbeit | 03.07.2026 |\n"
    units = [Unit(page=6, start_time=None, end_time=None,
                  raw_text="Zeitplan Abgabe Hausarbeit 03.07.2026 Praesentationen")]
    pages = {(4, 6): "Zeitplan. Abgabe Hausarbeit 03.07.2026 ist verbindlich. Ende."}
    sources = {4: {"source": {"id": 4, "file_type": "pdf"}, "is_media": False}}
    out = fill_uncited_lines(text, sources, _OffLoader({4: units}, pages)).splitlines()[0]
    assert out.endswith("|")                      # table row stays intact
    assert "[4, S. 6 @" in out                    # offset anchor present
    assert " ❘ " in out                           # non-pipe separator inside the cell
    # no stray pipe between the chip's opening and the closing cell pipe
    assert " | " not in out[out.index("[4, S. 6 @"):]
