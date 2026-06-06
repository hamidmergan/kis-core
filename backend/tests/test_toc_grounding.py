"""A table-of-contents / index must never be a citation target.

Two layers:
  - line level: _strip_toc_lines drops leader+page-number lines (solid OR spaced dots).
  - chunk level: a chunk that is mostly such lines is not a valid post-hoc attribution
    target (_is_toc_chunk -> filtered out of _pick_attribution).
"""
from src.features.ai_assistant.routes._helpers import (
    _strip_toc_lines,
    _is_toc_chunk,
    _pick_attribution,
)


# ── line level: spaced-dot leaders now caught too ────────────────────────────

def test_strips_solid_dot_leader():
    assert _strip_toc_lines("Vektorgrafik ........ 4").strip() == ""


def test_strips_spaced_dot_leader():
    assert _strip_toc_lines("Vektorgrafik . . . . . . 4").strip() == ""


def test_keeps_real_prose_with_trailing_number():
    line = "Die Abtastrate der CD beträgt 44,1 kHz und das Fernsehen nutzt 625 Zeilen"
    assert _strip_toc_lines(line) == line


def test_keeps_abbreviations():
    line = "Das ist z.B. wichtig und gilt seit 2016 für alle Module im Studiengang"
    assert _strip_toc_lines(line) == line


# ── chunk level: a mostly-TOC chunk is not a citation target ─────────────────

def test_toc_chunk_detected():
    toc = "\n".join([
        "Inhaltsverzeichnis",
        "1 Einleitung ........... 14",
        "1.2 Zu diesem Modul ........... 14",
        "2 Audio ........... 20",
        "3 Grafik ........... 60",
        "4 Video ........... 120",
    ])
    assert _is_toc_chunk(toc) is True


def test_prose_chunk_not_toc():
    prose = ("In diesem Modul behandeln wir die technischen Grundlagen der "
             "Medieninformatik, speziell die Technik audio-visueller Medien.")
    assert _is_toc_chunk(prose) is False


def test_short_chunk_not_toc():
    assert _is_toc_chunk("Audio") is False


# ── _pick_attribution skips TOC chunks ───────────────────────────────────────

def _hit(content, dist):
    return {"source_id": 1, "page_number": 3, "content": content, "vec_distance": dist}


def test_pick_skips_toc_chunk_even_if_closest():
    toc = "1 Einleitung ...... 14\n2 Audio ...... 20\n3 Grafik ...... 60\n4 Video ...... 120"
    prose = "Audio umfasst Sprache und Musik und wird digital abgetastet und gespeichert."
    # TOC chunk is closer, but must be skipped -> the prose chunk wins.
    best = _pick_attribution([_hit(toc, 0.10), _hit(prose, 0.30)], 0.6)
    assert best is not None and best["content"] == prose


def test_pick_returns_none_when_only_toc_in_gate():
    toc = "1 Einleitung ...... 14\n2 Audio ...... 20\n3 Grafik ...... 60\n4 Video ...... 120"
    assert _pick_attribution([_hit(toc, 0.10)], 0.6) is None
