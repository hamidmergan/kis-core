# backend/tests/test_citation_toc.py
"""Table-of-contents lines must never become evidence anchors."""
from src.features.ai_assistant.routes._text import _strip_toc_lines


def test_strips_dotted_leader_toc_line():
    txt = "2.2.1 Abtastrate: Grundlagen ............... 70"
    assert _strip_toc_lines(txt).strip() == ""        # whole index entry gone
    assert "Abtastrate" not in _strip_toc_lines(txt)


def test_keeps_real_prose_without_leaders():
    txt = "Quantisierung ist der Prozess, bei dem das Signal in Stufen umgewandelt wird."
    assert _strip_toc_lines(txt) == txt


def test_mixed_page_keeps_prose_drops_toc_line():
    txt = ("Einleitung zum Kapitel.\n"
           "Vektorgrafik ........................ 4\n"
           "Dann folgt normaler Fließtext.")
    out = _strip_toc_lines(txt)
    assert "Vektorgrafik" not in out                  # TOC entry dropped
    assert "Einleitung zum Kapitel." in out           # prose kept
    assert "Dann folgt normaler Fließtext." in out


def test_three_dot_ellipsis_in_prose_not_treated_as_toc():
    # A normal ellipsis is 3 dots; only runs of 4+ count as a leader.
    txt = "Das Ergebnis war ... 5 Prozent besser als erwartet."
    assert _strip_toc_lines(txt) == txt


def test_pure_toc_chunk_becomes_empty():
    txt = ("Audio ............ 54\n"
           "Grafik ........... 116\n"
           "Video ............ 200")
    assert _strip_toc_lines(txt).strip() == ""
