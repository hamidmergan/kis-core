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


def test_source_n_prior_keeps_citation_in_cited_source():
    # keyword matches source 3's text, but the chip says source 2 -> must stay in 2
    text = "[2, 05:00 | zotero citavi mendeline]"
    units = {
        2: [Unit(None, 1.0, 600.0, "etwas ganz anderes ohne diese begriffe")],
        3: [Unit(None, 10.0, 30.0, "literaturverwaltung zotero citavi mendeline tools")],
    }
    src = {2: {"source": {"id": 2}, "is_media": True},
           3: {"source": {"id": 3}, "is_media": True}}
    out = resolve_citation_positions(text, src, _Loader(units))
    assert "[2, 05:00 |" in out   # no match in src 2 -> media keeps typed time, still source 2
    assert "[3," not in out       # never re-attributed to source 3


def test_unknown_source_dropped_and_whitespace_tidied():
    text = "Foo [9, S. 2 | irgendwas] bar."
    src = {2: {"source": {"id": 2}, "is_media": False, "pages": {2}}}
    out = resolve_citation_positions(text, src, _Loader({2: []}))
    assert "[9" not in out
    assert "Foo bar." in out      # double space left by the drop is collapsed


def test_pdf_summary_only_page_kept_via_pages_set():
    # page 7 has no text chunk (no Unit) but IS a real page via the pages set
    text = "[4, S. 7 | unauffindbar]"
    units = {4: [Unit(13, None, None, "anderer seiteninhalt")]}
    src = {4: {"source": {"id": 4}, "is_media": False, "pages": {7, 13}}}
    out = resolve_citation_positions(text, src, _Loader(units))
    assert "[4, S. 7]" in out      # page kept (real page); unverified keyword dropped
    assert "unauffindbar" not in out


def test_pdf_unmatched_keyword_dropped_to_position_only():
    # An invented keyword that is on NO page (e.g. "Übersicht") must not be kept on
    # the chip — it can only mis-anchor. Keep the valid page, drop the keyword.
    text = "Wahrscheinlichkeitskapitel. [1, S. 91 | Übersicht]"
    units = {1: [Unit(91, None, None, "Kapitel 10 Wahrscheinlichkeitsrechnung Zufall Varianz")]}
    src = {1: {"source": {"id": 1}, "is_media": False, "pages": {91}}}
    out = resolve_citation_positions(text, src, _Loader(units))
    assert "[1, S. 91]" in out
    assert "Übersicht" not in out


def test_pdf_unverifiable_page_dropped():
    text = "Foo [4, S. 99 | unauffindbar] bar."
    units = {4: [Unit(13, None, None, "anderer seiteninhalt")]}
    src = {4: {"source": {"id": 4}, "is_media": False, "pages": {13}}}
    out = resolve_citation_positions(text, src, _Loader(units))
    assert "[4" not in out
    assert "Foo bar." in out


def test_pdf_keywordless_regrounds_from_line_to_correct_page():
    # The model cited page 7 with NO keyword; the line's own text actually lives on
    # page 8. Without a keyword the old resolver blindly kept the (wrong) typed page.
    text = "Passt die Frage zum Thema? [5, S. 7]"
    # unit bodies carry sentence punctuation, exactly as real page-chunks do, so the
    # anchor can be narrowed to the matched sentence.
    units = {5: [
        Unit(7, None, None, "Ist die Fragestellung zu einfach? Laesst die Frage sich "
                            "wissenschaftlich beantworten? Kann ich diese Fragestellung beantworten?"),
        Unit(8, None, None, "Ist die Frage so formuliert, dass sie eine gute Antwort "
                            "ermoeglicht? Passt die Fragestellung zum Thema? Manchmal passiert es."),
    ]}
    src = {5: {"source": {"id": 5}, "is_media": False, "pages": {7, 8}}}
    out = resolve_citation_positions(text, src, _Loader(units))
    assert "[5, S. 8" in out          # re-grounded from the wrong page 7 to page 8
    assert "[5, S. 7" not in out
    # anchor lands on the matched sentence, not the first bullet of the page
    anchor = out.split("[5, S. 8")[1]
    assert "Passt die" in anchor


def test_pdf_keywordless_kept_when_line_has_no_match():
    # No keyword AND the line does not match any unit -> keep the valid typed page,
    # do not invent an anchor.
    text = "Voellig anderes thema hier. [5, S. 7]"
    units = {5: [Unit(7, None, None, "ganz etwas anderes ohne bezug"),
                 Unit(8, None, None, "noch etwas vollkommen unverwandtes")]}
    src = {5: {"source": {"id": 5}, "is_media": False, "pages": {7, 8}}}
    out = resolve_citation_positions(text, src, _Loader(units))
    assert "[5, S. 7]" in out         # typed page kept, still keyword-less


def test_resolve_strips_html_markup_from_model_keyword():
    # Docling table chunks carry HTML; the model sometimes copies it into the keyword.
    text = "Peer-Review-Termin. [4, S. 6 | Peer-Review</b></td>]"
    units = {4: [Unit(6, None, None, "Zeitplan Online-Praesenz Peer-Review 29.05.2026 Uhr")]}
    src = {4: {"source": {"id": 4}, "is_media": False, "pages": {6}}}
    out = resolve_citation_positions(text, src, _Loader(units))
    assert "<" not in out and ">" not in out      # no raw HTML survives
    assert "</b>" not in out and "td]" not in out
    assert "[4, S. 6 | Peer-Review]" in out       # cleaned keyword


def test_pdf_ambiguous_heading_keyword_disambiguated_by_line():
    # keyword "Forschungsfrage Checkliste" is a heading present on BOTH page 7 and 8
    # -> ambiguous. The cited line's own text belongs to page 8, so page 8 wins
    # (not the model-typed 7).
    text = ("Ist die Frage so formuliert, keine Ja Nein Frage, keine schulische "
            "Eroerterung. [5, S. 7 | Forschungsfrage Checkliste]")
    units = {5: [
        Unit(7, None, None, "Forschungsfrage Checkliste Ist die Fragestellung zu einfach "
                            "Laesst die Frage wissenschaftlich beantworten Zugang Daten"),
        Unit(8, None, None, "Forschungsfrage Checkliste Ist die Frage so formuliert dass sie "
                            "eine gute Antwort ermoeglicht keine Ja Nein Frage keine schulische "
                            "Eroerterung Passt die Fragestellung zum Thema"),
    ]}
    src = {5: {"source": {"id": 5}, "is_media": False, "pages": {7, 8}}}
    out = resolve_citation_positions(text, src, _Loader(units))
    assert "[5, S. 8" in out
    assert "[5, S. 7" not in out


def test_pdf_line_overrides_confident_but_wrong_keyword_page():
    # The model attached a page-7 keyword to a page-8 claim. The keyword matches
    # page 7 EXACTLY, but the claim's own text belongs to page 8 -> the line wins.
    text = "Passt die Frage zum Thema? [5, S. 7 | Ist die Fragestellung zu einfach]"
    units = {5: [
        Unit(7, None, None, "Ist die Fragestellung zu einfach Laesst die Frage beantworten"),
        Unit(8, None, None, "Passt die Fragestellung zum Thema Manchmal driftet man ab"),
    ]}
    src = {5: {"source": {"id": 5}, "is_media": False, "pages": {7, 8}}}
    out = resolve_citation_positions(text, src, _Loader(units))
    assert "[5, S. 8" in out
    assert "[5, S. 7" not in out


def test_pdf_unique_keyword_page_not_overridden_by_line():
    # A keyword that uniquely identifies ONE page must be trusted even if the line
    # is generic -> no ambiguity, no override.
    text = "Zu den Zeitschriften. [5, S. 21 | ACM Transactions Computer Human Interaction]"
    units = {5: [
        Unit(20, None, None, "Rahmenprogramm Keynotes Workshops Poster Sessions"),
        Unit(21, None, None, "i-com ACM Transactions Computer Human Interaction Behaviour"),
    ]}
    src = {5: {"source": {"id": 5}, "is_media": False, "pages": {20, 21}}}
    out = resolve_citation_positions(text, src, _Loader(units))
    assert "[5, S. 21" in out


def test_pdf_keyword_page_not_overridden_when_line_matches_many_pages():
    # The keyword uniquely resolves to page 441. The cited line's own text, however,
    # appears VERBATIM on both page 42 and page 441 (same wording in an early
    # overview and again in the body). The line is therefore ambiguous and must NOT
    # override the keyword's page -> the chip must stay on 441, not jump to the
    # earliest page (42).
    text = "Die Methode wird angewendet [5, S. 441 | Methode wird angewendet beim Verfahren]"
    units = {5: [
        Unit(42, None, None, "Die Methode wird angewendet Einleitung Ueberblick"),
        Unit(441, None, None, "Die Methode wird angewendet beim Verfahren im Detail"),
    ]}
    src = {5: {"source": {"id": 5}, "is_media": False, "pages": {42, 441}}}
    out = resolve_citation_positions(text, src, _Loader(units))
    assert "[5, S. 441" in out
    assert "[5, S. 42 " not in out and "[5, S. 42]" not in out
