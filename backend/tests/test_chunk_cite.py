# backend/tests/test_chunk_cite.py
"""resolve_chunk_refs: the model cites the CHUNK it used (`[N, #C | kw]`); we verify
the claim is really in that chunk and emit a chip with the chunk's REAL page/timestamp.
Unknown/unverified chunk ids are dropped (the uncited-line filler is the safety net)."""
from src.features.ai_assistant.routes._chunk_cite import resolve_chunk_refs
from src.features.ai_assistant.routes._citation_match import Unit


def _seg(text, start):
    return Unit(page=None, start_time=start, end_time=start + 10, raw_text=text)


class _FakeLoader:
    """Stub SourceUnitLoader: configurable offset suffixes (PDF) + media segments."""
    def __init__(self, offset=None, segments=None):
        self._offset = offset or []
        self._segments = segments or []

    def offset_suffixes(self, source, page, claim):
        return list(self._offset)

    def units(self, source, *, is_media):
        return list(self._segments)


def _pdf_entry(qnum, page, content):
    return {"qnum": qnum, "source": {"id": qnum}, "is_media": False,
            "page": page, "start_time": None, "end_time": None, "content": content}


def _media_entry(qnum, start, end, content):
    return {"qnum": qnum, "source": {"id": qnum}, "is_media": True,
            "page": None, "start_time": start, "end_time": end, "content": content}


def test_pdf_chunk_ref_resolves_to_real_page():
    reg = {7: _pdf_entry(1, 440, "audio engineering society aes standardisierung norm")}
    line = "- Audio Engineering Society. [1, #7 | Audio Engineering Society]"
    had, out = resolve_chunk_refs(line, reg, _FakeLoader())
    assert had is True
    assert "[1, S. 440 | Audio Engineering Society]" in out
    assert "#" not in out                       # no raw chunk marker survives


def test_pdf_unverified_chunk_is_dropped():
    # The chunk is about audio; the claim is about something else -> not in the chunk.
    reg = {7: _pdf_entry(1, 440, "audio engineering society aes standardisierung norm")}
    line = "- Die Mensa hat dienstags immer Pizza im Angebot. [1, #7 | Mensa Pizza]"
    had, out = resolve_chunk_refs(line, reg, _FakeLoader())
    assert had is True
    assert "[1," not in out                      # chip dropped, claim text kept
    assert "Mensa" in out and "#" not in out


def test_unknown_chunk_id_is_dropped():
    line = "- Irgendeine Aussage hier. [1, #99 | Irgendeine Aussage]"
    had, out = resolve_chunk_refs(line, {}, _FakeLoader())
    assert had is True
    assert "[1," not in out and "#" not in out


def test_qnum_taken_from_chunk_not_from_typed_n():
    # Model typed N=1 but the chunk really belongs to source 2 -> chunk wins.
    reg = {7: _pdf_entry(2, 12, "zotero citavi literaturverwaltung mendeley tools")}
    line = "- Zotero Citavi Literaturverwaltung. [1, #7 | Zotero Citavi]"
    had, out = resolve_chunk_refs(line, reg, _FakeLoader())
    assert "[2, S. 12" in out
    assert "[1," not in out


def test_offset_suffix_used_when_available():
    reg = {7: _pdf_entry(1, 440, "audio engineering society aes norm")}
    loader = _FakeLoader(offset=["@10-40 | Audio Engineering Society"])
    line = "- Audio Engineering Society. [1, #7 | Audio Engineering Society]"
    had, out = resolve_chunk_refs(line, reg, loader)
    assert "[1, S. 440@10-40 | Audio Engineering Society]" in out


def test_media_chunk_uses_precise_window_segment_timestamp():
    # Chunk window is 1000-1080s; the finer transcript segment at 1040s matches the
    # claim (stem: Schneeballsystem ~ schneeballprinzip) -> precise 17:20, not 16:40.
    reg = {7: _media_entry(1, 1000.0, 1080.0,
                           "von einer quelle ausgehend schneeballprinzip weitere literatur")}
    loader = _FakeLoader(segments=[_seg("schneeballprinzip weitere literatur quelle", 1040.0)])
    line = "- Schneeballsystem und Literatur. [1, #7 | Schneeballsystem Literatur]"
    had, out = resolve_chunk_refs(line, reg, loader)
    assert "[1, 17:20 | Schneeballsystem Literatur]" in out


def test_media_falls_back_to_chunk_start_when_no_finer_segment():
    reg = {7: _media_entry(1, 1000.0, 1080.0,
                           "von einer quelle ausgehend schneeballprinzip weitere literatur")}
    loader = _FakeLoader(segments=[])                 # no finer segment
    line = "- Schneeballsystem und Literatur. [1, #7 | Schneeballsystem Literatur]"
    had, out = resolve_chunk_refs(line, reg, loader)
    assert "[1, 16:40 | Schneeballsystem Literatur]" in out   # 1000s -> 16:40


def test_multiple_chunk_chips_on_one_line_both_resolve():
    reg = {
        7: _pdf_entry(1, 440, "audio engineering society aes norm"),
        8: _pdf_entry(2, 12, "zotero citavi literaturverwaltung mendeley"),
    }
    line = ("- Audio Engineering Society und Zotero Citavi Literaturverwaltung. "
            "[1, #7 | Audio Engineering Society] [2, #8 | Zotero Citavi]")
    had, out = resolve_chunk_refs(line, reg, _FakeLoader())
    assert "[1, S. 440" in out and "[2, S. 12" in out
    assert "#" not in out


def test_line_without_chunk_ref_is_unchanged_and_had_false():
    line = "- Eine Aussage mit Alt-Format. [1, S. 5 | Aussage]"
    had, out = resolve_chunk_refs(line, {}, _FakeLoader())
    assert had is False
    assert out == line                            # legacy chip untouched -> legacy resolver handles it
