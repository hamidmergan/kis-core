import re
from src.features.ai_assistant.routes._helpers import (
    _running_furniture, _strip_furniture, _overlap_keyword, SourceUnitLoader, _kw_from_unit,
)
from src.features.ai_assistant.routes._citation_match import Unit

FOOTER = "06.05.2026\r\nWissenschaftliches Seminar - Lenka Kleinau, M.Sc.\r\n{n}\r\n"


def _chunk(page, body):
    return {"page_number": page, "content": FOOTER.format(n=page) + body, "start_time": None}


def test_running_furniture_detects_repeated_lines():
    chunks = [_chunk(1, "Erste Seite Inhalt"), _chunk(2, "Zweite Seite Inhalt"),
              _chunk(3, "Dritte Seite Inhalt")]
    f = _running_furniture(chunks)
    from src.features.ai_assistant.routes._helpers import _norm_for_match
    assert _norm_for_match("06.05.2026") in f
    assert _norm_for_match("Wissenschaftliches Seminar - Lenka Kleinau, M.Sc.") in f
    assert _norm_for_match("Erste Seite Inhalt") not in f  # body line, appears once


def test_running_furniture_needs_two_pages():
    assert _running_furniture([_chunk(1, "nur eine seite")]) == set()


def test_strip_furniture_removes_footer_and_page_number_keeps_case():
    from src.features.ai_assistant.routes._helpers import _norm_for_match
    f = {_norm_for_match("06.05.2026"), _norm_for_match("Wissenschaftliches Seminar - Lenka Kleinau, M.Sc.")}
    body = _strip_furniture(FOOTER.format(n=3) + "Upload-Bereich im Kurs freigeschaltet", f)
    assert "06.05.2026" not in body
    assert "Wissenschaftliches Seminar" not in body
    assert "Upload-Bereich im Kurs freigeschaltet" in body  # original case kept
    assert body.strip() != "" and "\n3\n" not in body  # standalone page-number line dropped


def test_loader_pdf_units_exclude_footer(monkeypatch):
    chunks = [_chunk(1, "Alpha Inhalt"), _chunk(2, "Beta Inhalt"),
              _chunk(3, "Upload-Bereich im Kurs freigeschaltet Vorgaben Ausarbeitung")]
    monkeypatch.setattr(
        "src.features.ai_assistant.repository.chunks.get_aia_chunks_by_source", lambda sid: chunks)
    units = SourceUnitLoader().units({"id": 9}, is_media=False)
    u3 = [u for u in units if u.page == 3][0]
    assert "06.05.2026" not in u3.raw_text
    assert "Wissenschaftliches Seminar" not in u3.raw_text
    assert "Upload-Bereich" in u3.raw_text
    # the keyword for this unit is now body, never the footer
    assert "06.05.2026" not in _kw_from_unit(u3)


def test_overlap_keyword_picks_body_phrase_in_line():
    u = Unit(page=3, start_time=None, end_time=None,
             raw_text="Upload-Bereich im Kurs 6-7 Seiten Länge zuzüglich Literaturverzeichnis")
    line = "- Umfang: 6–7 Seiten (ohne Verzeichnis) plus Literaturverzeichnis."
    kw = _overlap_keyword(line, u)
    # a verbatim body phrase that also occurs in the line (so it anchors the right spot)
    from src.features.ai_assistant.routes._helpers import _norm_for_match
    assert _norm_for_match(kw) in _norm_for_match(line)
    assert _norm_for_match(kw) in _norm_for_match(u.raw_text)
    assert "06.05" not in kw
