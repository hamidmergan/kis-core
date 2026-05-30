"""Tests for keyword-based citation page/timestamp re-grounding.

Verifies the core anti-hallucination guarantee: the model's free-typed page is
ignored; the real position is derived from the verbatim keyword, and citations
that cannot be grounded are dropped.
"""
from src.features.ai_assistant.routes._helpers import (
    _norm_for_match,
    _resolve_citation_pages,
    _strip_summary_citations,
    _chipify_inline_refs,
    _build_page_regions,
    _best_body_anchor,
)


def _qmap():
    return [
        {"qnum": 4, "uuid": "u1", "filename": "01_Einführung.pdf", "is_media": False},
        {"qnum": 1, "uuid": "u2", "filename": "VL1_25-03-2026.webm", "is_media": True},
    ]


def _pdf_index():
    # Source 1: a short PDF whose real pages are 2, 3, 7.
    return {
        1: {
            "is_media": False,
            "pages": {2, 3, 7},
            "chunks": [
                {"page": 2, "start_time": None,
                 "norm_content": _norm_for_match("Das Seminar wird von Lenka Kleinau geleitet.")},
                {"page": 3, "start_time": None,
                 "norm_content": _norm_for_match("Formate sind Keynotes, Workshops und ein Konferenz-Dinner.")},
                {"page": 7, "start_time": None,
                 "norm_content": _norm_for_match("Zitierstile sind IEEE und APA.")},
            ],
        }
    }


def test_overrides_hallucinated_page_with_real_page():
    # Model claims S. 44 (does not exist); keyword lives on page 3.
    out = _resolve_citation_pages("Foo. [1, S. 44 | Konferenz-Dinner]", _pdf_index())
    assert out == "Foo. [1, S. 3 | Konferenz-Dinner]"


def test_keeps_correct_page_when_model_was_right():
    out = _resolve_citation_pages("Foo. [1, S. 3 | Keynotes, Workshops]", _pdf_index())
    assert out == "Foo. [1, S. 3 | Keynotes, Workshops]"


def test_drops_citation_when_page_fake_and_keyword_absent():
    # Keyword not in any chunk AND page 44 doesn't exist -> hallucination -> drop.
    out = _resolve_citation_pages("Foo. [1, S. 44 | voellig erfundener text]", _pdf_index())
    assert out == "Foo. "


def test_keeps_real_image_page_without_keyword_match():
    # Page 7 is real; keyword can't be matched (e.g. image/scan) -> keep page 7.
    out = _resolve_citation_pages("Foo. [1, S. 7 | text der nicht im chunk steht]", _pdf_index())
    assert out == "Foo. [1, S. 7 | text der nicht im chunk steht]"


def test_drops_unknown_source():
    out = _resolve_citation_pages("Foo. [9, S. 3 | Konferenz-Dinner]", _pdf_index())
    assert out == "Foo. "


def test_special_hyphen_keyword_still_matches():
    # Chunk has non-breaking hyphen U+2011; model wrote a normal hyphen.
    idx = {
        1: {
            "is_media": False,
            "pages": {5},
            "chunks": [
                {"page": 5, "start_time": None,
                 "norm_content": _norm_for_match("Das Peer‑Review‑Verfahren gibt Feedback.")},
            ],
        }
    }
    out = _resolve_citation_pages("X. [1, S. 99 | Peer-Review-Verfahren]", idx)
    assert out == "X. [1, S. 5 | Peer-Review-Verfahren]"


def test_relocates_to_sibling_chunk_with_keyword():
    # Model cited page 2, but the keyword actually lives on page 7.
    out = _resolve_citation_pages("Foo. [1, S. 2 | IEEE und APA]", _pdf_index())
    assert out == "Foo. [1, S. 7 | IEEE und APA]"


def test_media_timestamp_from_keyword_chunk():
    idx = {
        1: {
            "is_media": True,
            "pages": set(),
            "chunks": [
                {"page": None, "start_time": 0.0,
                 "norm_content": _norm_for_match("Begruessung und Organisatorisches.")},
                {"page": None, "start_time": 754.0,
                 "norm_content": _norm_for_match("Wir besprechen Stars and Bars im Detail.")},
            ],
        }
    }
    out = _resolve_citation_pages("Im Video. [1, 02:00 | Stars and Bars]", idx)
    assert out == "Im Video. [1, 12:34 | Stars and Bars]"  # 754s -> 12:34


def test_media_keeps_typed_timestamp_when_keyword_not_found():
    # A video/audio timestamp is always a valid seek target, so an unmatched
    # keyword keeps the typed timestamp (media analog of keeping a real PDF page).
    idx = {
        1: {
            "is_media": True,
            "pages": set(),
            "chunks": [
                {"page": None, "start_time": 10.0,
                 "norm_content": _norm_for_match("Begruessung.")},
            ],
        }
    }
    out = _resolve_citation_pages("Foo. [1, 05:00 | paraphrasiertes thema]", idx)
    assert out == "Foo. [1, 05:00 | paraphrasiertes thema]"


def test_media_normalizes_typed_timestamp():
    # "5:00" -> "05:00" via parse+format, even without a keyword match.
    idx = {1: {"is_media": True, "pages": set(),
               "chunks": [{"page": None, "start_time": 0.0,
                           "norm_content": _norm_for_match("Intro.")}]}}
    assert _resolve_citation_pages("X. [1, 5:00 | nicht da]", idx) == "X. [1, 05:00 | nicht da]"


def test_media_keyword_match_still_overrides_typed_timestamp():
    # Rule 2 unchanged: a matched keyword still relocates to the chunk's real time.
    idx = {1: {"is_media": True, "pages": set(),
               "chunks": [{"page": None, "start_time": 754.0,
                           "norm_content": _norm_for_match("Stars and Bars im Detail.")}]}}
    assert _resolve_citation_pages("V. [1, 02:00 | Stars and Bars]", idx) == "V. [1, 12:34 | Stars and Bars]"


def test_media_page_citation_still_dropped():
    # A page number on a media source is bogus (no timestamp) -> still dropped.
    idx = {1: {"is_media": True, "pages": set(),
               "chunks": [{"page": None, "start_time": 10.0,
                           "norm_content": _norm_for_match("Begruessung und Intro.")}]}}
    assert _resolve_citation_pages("Foo. [1, S. 3 | voellig erfunden]", idx) == "Foo. "


def test_citation_without_keyword_keeps_real_page():
    out = _resolve_citation_pages("Foo. [1, S. 2]", _pdf_index())
    assert out == "Foo. [1, S. 2]"


def test_multiple_citations_mixed():
    text = (
        "Lenka leitet. [1, S. 1 | Lenka Kleinau] "
        "Formate gibt es. [1, S. 99 | Konferenz-Dinner] "
        "Quatsch. [1, S. 50 | erfunden xyz]"
    )
    out = _resolve_citation_pages(text, _pdf_index())
    # 1st -> relocated to page 2 (keyword match), 2nd -> page 3, 3rd -> dropped.
    assert out == (
        "Lenka leitet. [1, S. 2 | Lenka Kleinau] "
        "Formate gibt es. [1, S. 3 | Konferenz-Dinner] "
        "Quatsch. "
    )


def test_rejects_keyword_match_on_fake_page():
    # Simulates a hallucinated doc-summary [p.44]: the in-context chunk carries
    # page 44, but the source's real pages are only {3}. Even though the keyword
    # matches that chunk, page 44 is not real -> citation dropped.
    idx = {
        1: {
            "is_media": False,
            "pages": {3},
            "chunks": [
                {"page": 44, "start_time": None,
                 "norm_content": _norm_for_match("Formate sind Konferenz-Dinner.")},
            ],
        }
    }
    assert _resolve_citation_pages("X. [1, S. 44 | Konferenz-Dinner]", idx) == "X. "


def test_prefers_real_page_sibling_over_fake_page():
    # Same keyword on a fake-page chunk AND a real-page chunk -> use the real one.
    idx = {
        1: {
            "is_media": False,
            "pages": {3},
            "chunks": [
                {"page": 44, "start_time": None,
                 "norm_content": _norm_for_match("Konferenz-Dinner irgendwo.")},
                {"page": 3, "start_time": None,
                 "norm_content": _norm_for_match("Auf Tagungen gibt es ein Konferenz-Dinner.")},
            ],
        }
    }
    assert _resolve_citation_pages("X. [1, S. 99 | Konferenz-Dinner]", idx) == "X. [1, S. 3 | Konferenz-Dinner]"


def test_page_range_grounds_to_keyword_page():
    # Model wrote a page RANGE "S. 6-7" (mimicking a section marker). We take the
    # first page, but the keyword relocates it to its real page 7 anyway.
    out = _resolve_citation_pages("Foo. [1, S. 6-7 | IEEE und APA]", _pdf_index())
    assert out == "Foo. [1, S. 7 | IEEE und APA]"


def test_page_range_with_section_marker_becomes_clean_chip():
    # The exact broken form the user reported: range + '❘' + uppercase heading.
    # Keyword 'ZITATARTEN' isn't in any chunk, but first page 2 is real -> the
    # citation is rebuilt as a clean single-page chip, never leaked as raw text.
    out = _resolve_citation_pages("Foo. [1, S. 2-3 ❘ ZITATARTEN]", _pdf_index())
    assert out == "Foo. [1, S. 2 | ZITATARTEN]"


def test_page_range_dropped_when_fake_and_keyword_absent():
    # Range starts on a non-existent page and the keyword can't be grounded -> drop.
    out = _resolve_citation_pages("Foo. [1, S. 50-55 | erfundener abschnitt]", _pdf_index())
    assert out == "Foo. "


def test_empty_index_is_noop():
    assert _resolve_citation_pages("Foo. [1, S. 3 | x]", {}) == "Foo. [1, S. 3 | x]"


# ─── Inline-reference chipification ─────────────────────────────────────────

def test_inline_pdf_ref_becomes_chip():
    out = _chipify_inline_refs("Webkonferenz am 15.04. (siehe PDF 01 S. 6).", _qmap())
    assert out == "Webkonferenz am 15.04. [4, S. 6]."


def test_inline_video_ref_becomes_chip():
    out = _chipify_inline_refs("Im Video (VL1, 12:07) wird das erklärt.", _qmap())
    assert out == "Im Video [1, 12:07] wird das erklärt."


def test_clock_time_in_parens_is_preserved():
    # "17:30" here is a time of day, NOT a video timestamp (no Video/VL token).
    s = "Sprechstunde (Mittwoch 17:30-18:30 Uhr) wird angeboten."
    assert _chipify_inline_refs(s, _qmap()) == s


def test_unmappable_inline_page_ref_is_dropped():
    # No source token to map -> drop the broken parenthetical rather than leave it.
    out = _chipify_inline_refs("Das Thema (siehe S. 6) ist wichtig.", _qmap())
    assert out == "Das Thema ist wichtig."


def test_non_position_parenthetical_is_kept():
    s = "Die Hausarbeit (ca. 2 Seiten) wird abgegeben."
    assert _chipify_inline_refs(s, _qmap()) == s


def test_chipify_noop_without_qmap():
    s = "Text (siehe PDF 01 S. 6)."
    assert _chipify_inline_refs(s, []) == s


def test_inline_seite_word_form_unmappable_is_dropped():
    # "(Seiten 6-7)" / "(Seite 9)" word-form page refs with no source -> dropped.
    out = _chipify_inline_refs("Zitatarten (Seiten 6-7) und Verweise (Seite 9).", _qmap())
    assert out == "Zitatarten und Verweise."


def test_inline_seite_word_form_with_source_becomes_chip():
    out = _chipify_inline_refs("Erklärt (siehe Seite 6 in PDF 01).", _qmap())
    assert out == "Erklärt [4, S. 6]."


def test_inline_seitenzahl_does_not_eat_page_count_prose():
    # "(ca. 2 Seiten)" is a length, not a page ref -> preserved.
    s = "Die Hausarbeit (ca. 2 Seiten) wird abgegeben."
    assert _chipify_inline_refs(s, _qmap()) == s


# ─── Summary-section citation stripping ─────────────────────────────────────

def test_summary_citations_stripped_body_kept():
    text = (
        "Das Seminar startet. [1, S. 2 | Seminar]\n\n"
        "## Zusammenfassung\n\n"
        "Insgesamt ein guter Kurs. [4, S. 6 | Kurs] [4, S. 3 | Abgabe]"
    )
    out = _strip_summary_citations(text)
    assert out == (
        "Das Seminar startet. [1, S. 2 | Seminar]\n\n"
        "## Zusammenfassung\n\n"
        "Insgesamt ein guter Kurs."
    )


def test_plain_summary_heading_without_hashes_also_strips():
    text = "Body. [1, S. 2 | x]\n\nZusammenfassung\n\nRecap ohne Quelle. [2, 12:07 | y]"
    out = _strip_summary_citations(text)
    assert out == "Body. [1, S. 2 | x]\n\nZusammenfassung\n\nRecap ohne Quelle."


def test_mid_text_summary_bullet_is_not_treated_as_heading():
    # "Zusammenfassung von Quellen" is a content bullet, NOT the closing heading.
    # Its citation must be preserved.
    text = "- **Zusammenfassung von Quellen**: eigene Kurzfassungen [6, 43:21 | Kurzfassungen]."
    assert _strip_summary_citations(text) == text


def test_no_summary_heading_is_noop():
    text = "Nur Fließtext. [1, S. 2 | x] Mehr Text. [2, 03:00 | y]"
    assert _strip_summary_citations(text) == text


# ─── Header/footer de-weighting (_build_page_regions / _reroute_to_body) ─────
# Mirrors the REAL stored chunk format: docling layout HTML with one labelled
# <div> per region (Page-Footer/Header = furniture, everything else = body),
# preceded by a duplicated plain-text rendering that must be IGNORED. The footer
# "Mentorin Lenka Kleinau, M.Sc." sits on the COVER (page 1); page 2 is the body
# slide that actually introduces the mentor.

_FOOTER = "Wissenschaftliches Seminar - Einführung - Lenka Kleinau, M.Sc."


def _foot(txt):
    return f'<div data-bbox="0 900 500 950" data-label="Page-Footer"><p>{txt}</p></div>'


def _mentor_chunks():
    return [
        # Cover: title + a footer credit naming the mentor (NOT body content).
        {"page_number": 1, "content":
            "Wissenschaftliches Seminar\nEinführung\nMentorin Lenka Kleinau, M.Sc.\n1\n"
            '<div data-label="Title"><h1>Wissenschaftliches Seminar</h1></div>'
            '<div data-label="Section-Header"><h2>Einführung</h2></div>'
            + _foot("Mentorin Lenka Kleinau, M.Sc.")
            + _foot("Folieninhalte nach Sophie Jent")},
        # Body slide: the mentor introduced as real content + the running footer.
        {"page_number": 2, "content":
            "Lenka Kleinau\nKontakt\n2\n"
            '<div data-label="Section-Header"><h2>MENTORIN UND TUTORIN DES MODULS</h2></div>'
            '<div data-label="Text"><p>Lenka Kleinau</p></div>'
            '<div data-label="List-Group"><ul><li>Kontakt: lenka.kleinau@th-luebeck.de</li></ul></div>'
            + _foot(_FOOTER)},
        {"page_number": 3, "content":
            "Kurskonzept\nPrüfungsleistung\n3\n"
            '<div data-label="List-Group"><ul><li>Kurskonzept</li><li>Prüfungsleistung</li></ul></div>'
            + _foot(_FOOTER)},
        {"page_number": 4, "content":
            "Themenfindung\n4\n"
            '<div data-label="List-Group"><ul><li>Themenfindung</li><li>Literaturrecherche</li></ul></div>'
            + _foot(_FOOTER)},
    ]


def test_build_page_regions_splits_body_and_boiler():
    reg = _build_page_regions(_mentor_chunks())
    # Cover footer credit is boilerplate on page 1, not body.
    assert "lenka kleinau" not in reg[1]["body"]
    assert "lenka kleinau" in reg[1]["boiler"]
    # Page 2 introduces the mentor in the BODY.
    assert "lenka kleinau" in reg[2]["body"]
    # The running footer is boilerplate on every content page.
    assert "lenka kleinau" not in reg[3]["body"]
    assert _norm_for_match(_FOOTER) in reg[3]["boiler"]
    # The duplicated plain-text rendering must NOT leak into body.
    assert "prüfungsleistung" in reg[3]["body"]


def _mentor_index():
    # Summaries the model saw: page 1 says "Mentor: Lenka Kleinau" (from the cover
    # footer), page 2 is the real mentor slide. The model cites S.1 with keyword
    # "Mentor Lenka Kleinau"; the colon makes it miss rule-2 -> rule-3 keeps S.1
    # unless the footer de-weighting re-grounds it.
    return {
        4: {
            "is_media": False,
            "pages": {1, 2, 3, 4},
            "chunks": [
                {"page": 1, "start_time": None,
                 "norm_content": _norm_for_match("Einführung. Mentor: Lenka Kleinau, M.Sc.")},
                {"page": 2, "start_time": None,
                 "norm_content": _norm_for_match("Mentorin und Tutorinnen: Lenka Kleinau. Kontakt.")},
                {"page": 3, "start_time": None,
                 "norm_content": _norm_for_match("Inhalte: Kurskonzept, Prüfungsleistung.")},
            ],
            "page_regions": _build_page_regions(_mentor_chunks()),
        }
    }


def test_reroutes_footer_credit_to_body_page():
    # Cover footer match (S.1) re-grounds to the body slide (S.2).
    out = _resolve_citation_pages("Mentorin ist Lenka Kleinau. [4, S. 1 | Mentor Lenka Kleinau]", _mentor_index())
    assert out == "Mentorin ist Lenka Kleinau. [4, S. 2 | Mentor Lenka Kleinau]"


def test_genuine_body_match_is_not_rerouted():
    # "Prüfungsleistung" is real body content on page 3 -> stays.
    out = _resolve_citation_pages("X. [4, S. 3 | Prüfungsleistung]", _mentor_index())
    assert out == "X. [4, S. 3 | Prüfungsleistung]"


def test_no_reroute_without_page_regions():
    # Same data but no page_regions attached -> behaves as before (keeps S.1).
    idx = _mentor_index()
    del idx[4]["page_regions"]
    out = _resolve_citation_pages("X. [4, S. 1 | Mentor Lenka Kleinau]", idx)
    assert out == "X. [4, S. 1 | Mentor Lenka Kleinau]"


def test_no_reroute_when_term_ambiguous_across_body_pages():
    # If the anchor appears as body on TWO pages, it's ambiguous -> keep model page.
    chunks = _mentor_chunks()
    chunks.append({"page_number": 5, "content":
        "noch\n5\n"
        '<div data-label="Text"><p>Nochmal Lenka Kleinau im Body</p></div>' + _foot(_FOOTER)})
    idx = _mentor_index()
    idx[4]["pages"] = {1, 2, 3, 4, 5}
    idx[4]["page_regions"] = _build_page_regions(chunks)
    out = _resolve_citation_pages("X. [4, S. 1 | Mentor Lenka Kleinau]", idx)
    assert out == "X. [4, S. 1 | Mentor Lenka Kleinau]"


def test_boilerplate_only_term_stays_on_model_page():
    # "Folieninhalte nach Sophie" exists ONLY in the page-1 footer (no body page)
    # -> no single body target -> keep the model's page (footer stays a fallback).
    out = _resolve_citation_pages("X. [4, S. 3 | Folieninhalte nach Sophie]", _mentor_index())
    assert out == "X. [4, S. 3 | Folieninhalte nach Sophie]"


def test_footer_deweighting_is_language_agnostic():
    # Same structure, English PDF: footer credit on cover, body slide on page 2.
    foot = "Scientific Seminar - Introduction - Jane Doe, M.Sc."
    efoot = lambda t: f'<div data-bbox="0 900 500 950" data-label="Page-Footer"><p>{t}</p></div>'
    chunks = [
        {"page_number": 1, "content":
            "Scientific Seminar\n1\n"
            '<div data-label="Title"><h1>Scientific Seminar</h1></div>'
            '<div data-label="Section-Header"><h2>Introduction</h2></div>'
            + efoot("Mentor Jane Doe, M.Sc.")},
        {"page_number": 2, "content":
            "Jane Doe\n2\n"
            '<div data-label="Section-Header"><h2>MENTOR OF THE MODULE</h2></div>'
            '<div data-label="Text"><p>Jane Doe</p></div>'
            '<div data-label="List-Group"><ul><li>Contact: jane.doe@uni.edu</li></ul></div>'
            + efoot(foot)},
        {"page_number": 3, "content":
            "Schedule\n3\n"
            '<div data-label="List-Group"><ul><li>Schedule</li><li>Grading</li></ul></div>'
            + efoot(foot)},
    ]
    idx = {
        4: {
            "is_media": False,
            "pages": {1, 2, 3},
            "chunks": [
                {"page": 1, "start_time": None, "norm_content": _norm_for_match("Introduction. Mentor: Jane Doe.")},
                {"page": 2, "start_time": None, "norm_content": _norm_for_match("Mentor of the module: Jane Doe. Contact.")},
            ],
            "page_regions": _build_page_regions(chunks),
        }
    }
    out = _resolve_citation_pages("The mentor is Jane Doe. [4, S. 1 | Mentor Jane Doe]", idx)
    assert out == "The mentor is Jane Doe. [4, S. 2 | Mentor Jane Doe]"


def test_best_body_anchor_picks_longest_grounded_subphrase():
    reg = _build_page_regions(_mentor_chunks())
    # "mentor lenka kleinau" isn't contiguous in any body; "lenka kleinau" is.
    assert _best_body_anchor("mentor lenka kleinau", reg) == "lenka kleinau"
    # A single-token keyword yields no anchor (needs >= 2 tokens).
    assert _best_body_anchor("kleinau", reg) is None
