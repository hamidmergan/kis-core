"""The collapse-fold must drop OCR/line-break join artifacts so a citation span
survives them. OCR'd PDFs (e.g. Docling output) insert U+FFFE or a soft hyphen at a
hyphenated line break ("Bachelor￾Studiengangs"), while the live pdfium text layer
has the joined word or a different separator. Folding both sides to the same artifact-
free string lets the offset/keyword anchor match. MUST mirror the frontend _collapseFold.
"""
from src.features.ai_assistant.routes._page_geometry import _collapse_fold


def test_strips_ufffe_join_artifact():
    clean, c2t = _collapse_fold("Bachelor￾Studiengangs")
    assert clean == "bachelorstudiengangs"
    assert len(c2t) == len(clean)
    # "Bachelor" = raw 0..7; artifact at raw 8 is skipped; "S" of Studiengangs = raw 9.
    assert c2t[0] == 0
    assert c2t[8] == 9


def test_strips_soft_hyphen():
    clean, _ = _collapse_fold("Kla­ren")
    assert clean == "klaren"


def test_strips_zero_width_and_bom():
    clean, _ = _collapse_fold("a​﻿‍b")
    assert clean == "ab"


def test_clean_text_unchanged():
    clean, c2t = _collapse_fold("Hallo Welt")
    assert clean == "hallo welt"
    assert c2t == [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
