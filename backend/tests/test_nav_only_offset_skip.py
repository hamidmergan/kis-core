"""nav-only offset skip: when highlights are OFF, the grounding functions must NOT
compute @start-end span offsets. The page stays identical — only the (discarded) span
is skipped. Each test asserts both the output (no '@' marker) AND that offset_suffixes
is never called. Default (with_offsets=True) keeps computing offsets (existing tests).
"""
from src.features.ai_assistant.routes._chunk_cite import resolve_chunk_refs
from src.features.ai_assistant.routes._helpers import (
    resolve_citation_positions, fill_uncited_lines, _needs_attribution,
)
from src.features.ai_assistant.routes._citation_match import Unit


class _RecordingLoader:
    """Records whether offset_suffixes was called; returns a fake span when it is."""
    def __init__(self, units_by_src=None):
        self.offset_called = False
        self._units = units_by_src or {}

    def offset_suffixes(self, source, page, claim):
        self.offset_called = True
        return [" @0-5 | span"]

    def offset_suffix(self, source, page, claim):
        self.offset_called = True
        return " @0-5 | span"

    def units(self, source, *, is_media):
        return list(self._units.get(source["id"], []))


def _pdf_entry(qnum, page, content):
    return {"qnum": qnum, "source": {"id": qnum}, "is_media": False,
            "page": page, "start_time": None, "end_time": None, "content": content}


# ── resolve_chunk_refs ───────────────────────────────────────────────────────

def test_chunk_refs_skips_offsets_when_disabled():
    reg = {7: _pdf_entry(1, 440, "audio engineering society aes standardisierung norm")}
    line = "- Audio Engineering Society. [1, #7 | Audio Engineering Society]"
    loader = _RecordingLoader()
    had, out = resolve_chunk_refs(line, reg, loader, with_offsets=False)
    assert had is True
    assert "@" not in out                   # no span computed
    assert loader.offset_called is False     # offset_suffixes never called
    assert "[1, S. 440" in out              # page preserved


def test_chunk_refs_uses_offsets_by_default():
    reg = {7: _pdf_entry(1, 440, "audio engineering society aes standardisierung norm")}
    line = "- Audio Engineering Society. [1, #7 | Audio Engineering Society]"
    loader = _RecordingLoader()
    had, out = resolve_chunk_refs(line, reg, loader)  # default with_offsets=True
    assert loader.offset_called is True
    assert "@0-5" in out


# ── resolve_citation_positions ───────────────────────────────────────────────

def test_citation_positions_skips_offsets_when_disabled():
    text = "Passt die Frage zum Thema? [5, S. 8 | Passt die Fragestellung]"
    units = {5: [Unit(8, None, None, "Passt die Fragestellung zum Thema Manchmal driftet man ab")]}
    src = {5: {"source": {"id": 5, "file_type": "pdf"}, "is_media": False, "pages": {8}}}
    loader = _RecordingLoader(units)
    out = resolve_citation_positions(text, src, loader, with_offsets=False)
    assert "@" not in out
    assert loader.offset_called is False
    assert "[5, S. 8" in out


# ── fill_uncited_lines ───────────────────────────────────────────────────────

def test_fill_skips_offsets_when_disabled():
    line = "Die Fragestellung passt zum Thema der Arbeit."
    units = {5: [Unit(8, None, None, "Die Fragestellung passt zum Thema der Arbeit")]}
    src = {5: {"source": {"id": 5}, "is_media": False}}
    loader = _RecordingLoader(units)
    out = fill_uncited_lines(line, src, loader, with_offsets=False)
    assert loader.offset_called is False
    assert "[5, S. 8" in out                 # chip still produced (page reached), just no span
    assert "@" not in out


# ── _needs_attribution (gate parity for batch pre-embedding) ──────────────────

def test_needs_attribution_gate():
    assert _needs_attribution("Eine inhaltlich substanzielle Aussage zum Thema.") is True
    assert _needs_attribution("## Überblick") is False               # too short / heading
    assert _needs_attribution("Fakt mit Quelle hier drin. [1, S. 3 | Fakt]") is False  # already cited
