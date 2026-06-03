# backend/tests/test_citation_toc.py
"""Table-of-contents / index entries must not become citation anchors. A TOC line
('Vektorgrafik ............... 4') contains the topic keyword verbatim, so a claim
about that topic would otherwise ground to the index page instead of the real content
section. We drop such lines (dotted leader + trailing page number) before matching —
per line, so real prose on the same chunk survives. Language-agnostic (structure only,
no wordlist)."""
from src.features.ai_assistant.routes._helpers import _strip_toc_lines
from src.features.ai_assistant.routes._citation_match import Unit, match_query


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


def test_toc_stripped_unit_does_not_match_but_prose_does():
    # Behaviour contract: the same keyword matches a real prose unit but NOT a unit
    # whose only mention sat in a (now stripped) TOC line.
    toc = "Vektorgrafik ................. 4\nRastergrafik ............ 5"
    prose = "Eine Vektorgrafik beschreibt Bilder durch mathematische Pfade und Kurven."
    u_toc = Unit(page=4, start_time=None, end_time=None, raw_text=_strip_toc_lines(toc))
    u_prose = Unit(page=130, start_time=None, end_time=None, raw_text=_strip_toc_lines(prose))
    assert match_query("Vektorgrafik", [u_toc]).unit is None
    assert match_query("Vektorgrafik", [u_prose]).unit is not None
