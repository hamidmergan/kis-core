from src.features.ai_assistant.routes._helpers import fill_uncited_lines
from src.features.ai_assistant.routes._citation_match import Unit


class _FakeLoader:
    def __init__(self, units): self._u = units
    def units(self, source, *, is_media): return self._u


def test_fills_only_uncited_groundable_lines():
    text = (
        "## Überblick\n"
        "- Das Paper hat sechs bis sieben Seiten.\n"
        "- Schon zitiert. [2, S. 5 | foo]\n"
    )
    units = [Unit(page=5, start_time=None, end_time=None,
                  raw_text="das Paper hat sechs bis sieben Seiten plus Literaturverzeichnis")]
    sources = {2: {"source": {"id": 2, "filename": "x.pdf"}, "is_media": False}}
    out = fill_uncited_lines(text, sources, _FakeLoader(units))
    lines = out.splitlines()
    assert lines[0] == "## Überblick"            # heading untouched
    assert "[2, S. 5 |" in lines[1]              # first bullet now cited
    assert "[2, S. 5 | foo]" in lines[2]         # pre-existing citation untouched
    assert out.count("[2, S. 5 |") == 2          # one added + one pre-existing


def test_in_summary_suppresses_fill():
    text = "## Zusammenfassung\n- Ein Recap-Punkt.\n"
    units = [Unit(page=5, start_time=None, end_time=None, raw_text="ein recap punkt aus der quelle")]
    sources = {2: {"source": {"id": 2}, "is_media": False}}
    out = fill_uncited_lines(text, sources, _FakeLoader(units))
    assert "[2," not in out  # nothing cited after the summary heading


def test_no_match_leaves_line_uncited():
    text = "- Etwas völlig anderes.\n"
    units = [Unit(page=5, start_time=None, end_time=None, raw_text="komplett unzusammenhängender text")]
    sources = {2: {"source": {"id": 2}, "is_media": False}}
    out = fill_uncited_lines(text, sources, _FakeLoader(units))
    assert "[2," not in out


def test_media_emits_timestamp_format():
    text = "- Peer Review unter Studierenden.\n"
    units = [Unit(page=None, start_time=476.0, end_time=492.0,
                  raw_text="peer review unter studierenden feedback")]
    sources = {1: {"source": {"id": 1}, "is_media": True}}
    out = fill_uncited_lines(text, sources, _FakeLoader(units))
    assert "[1, 07:56 |" in out  # 476s -> 07:56 (MM:SS), not S.


def test_html_markup_stripped_from_filled_keyword():
    # Page-chunk text from a docling table is full of HTML; the appended keyword
    # must be clean visible text, never tag markup.
    text = "- Online-Praesenz Peer-Review am 29.05.2026.\n"
    units = [Unit(page=6, start_time=None, end_time=None,
                  raw_text='<div data-label="Table"> <td><b>Online-Praesenz: Peer-Review</b></td> '
                           '<td><b>29.05.2026, 14:30-19:00 Uhr</b></td> </div>')]
    sources = {4: {"source": {"id": 4}, "is_media": False}}
    out = fill_uncited_lines(text, sources, _FakeLoader(units))
    assert "[4, S. 6 |" in out
    kw = out.split("[4, S. 6 |")[1].split("]")[0]
    assert "<" not in kw and ">" not in kw          # no tag brackets
    assert "td" not in kw.split() and "b" not in kw.split()  # no tag-name tokens
    assert "Peer-Review" in kw                       # clean cell text anchors


def test_table_row_citation_inserted_inside_last_cell():
    # A markdown table data row must get its chip INSIDE the last cell (with the
    # non-pipe ❘ separator) so the table renders the chip; appended after the row
    # the markdown parser drops it.
    text = "| Abgabe Hausarbeit | 03.07.2026 |\n"
    units = [Unit(page=6, start_time=None, end_time=None,
                  raw_text="Zeitplan Abgabe Hausarbeit 03.07.2026 Praesentationen")]
    sources = {4: {"source": {"id": 4}, "is_media": False}}
    out = fill_uncited_lines(text, sources, _FakeLoader(units)).splitlines()[0]
    assert out.endswith("|")                 # row still closes with a pipe -> table intact
    assert "[4, S. 6 ❘" in out               # chip uses the non-pipe separator
    assert " | " not in out[out.index("[4, S. 6 ❘"):]  # no stray pipe after the chip opens
    assert out.index("[4, S. 6 ❘") < out.rindex("|")    # chip sits before the closing pipe


def test_table_header_row_not_cited():
    # The header row (directly above the |---| delimiter) is a column title, not a
    # claim, and must never get a chip.
    text = ("| Aktivität | Termin |\n"
            "|-----------|--------|\n"
            "| Abgabe Hausarbeit | 03.07.2026 |\n")
    units = [Unit(page=6, start_time=None, end_time=None,
                  raw_text="Aktivität Termin Abgabe Hausarbeit 03.07.2026")]
    sources = {4: {"source": {"id": 4}, "is_media": False}}
    out = fill_uncited_lines(text, sources, _FakeLoader(units)).splitlines()
    assert out[0] == "| Aktivität | Termin |"      # header untouched
    assert "[4" not in out[0]
    assert "[4, S. 6 ❘" in out[2]                  # data row still cited


def test_table_row_already_cited_in_cell_not_double_filled():
    # A table row whose last cell already carries a chip must not be filled again.
    text = "| Abgabe Hausarbeit | 03.07.2026 [4, S. 6 ❘ Abgabe Hausarbeit] |\n"
    units = [Unit(page=6, start_time=None, end_time=None,
                  raw_text="Zeitplan Abgabe Hausarbeit 03.07.2026")]
    sources = {4: {"source": {"id": 4}, "is_media": False}}
    out = fill_uncited_lines(text, sources, _FakeLoader(units))
    assert out.count("[4, S. 6") == 1        # not doubled


def test_main_clause_fallback_fills_bullet_with_parenthetical_gloss():
    # The full bullet carries an author gloss in parentheses that is NOT in the
    # source, dragging containment below threshold. The main clause (before the
    # parenthesis) still grounds confidently.
    text = "- Passt die Frage zum Thema? (Kein Abdriften waehrend der Recherche.)\n"
    units = [
        Unit(page=7, start_time=None, end_time=None,
             raw_text="Ist die Fragestellung zu einfach Laesst die Frage beantworten"),
        Unit(page=8, start_time=None, end_time=None,
             raw_text="Passt die Fragestellung zum Thema Manchmal driftet man ab"),
    ]
    sources = {5: {"source": {"id": 5}, "is_media": False}}
    out = fill_uncited_lines(text, sources, _FakeLoader(units))
    assert "[5, S. 8 |" in out      # filled via the main clause, on the right page


def test_ambiguous_line_gets_one_chip_per_near_tie_page():
    # The claim's text appears equally well on two pages of the SAME source (e.g. a
    # glossary term spanning the Abkuerzungsverzeichnis pages). Instead of dropping the
    # chip the filler emits one chip per near-tie page -> the user sees both, never none.
    text = "- Audio Engineering Society.\n"
    units = [
        Unit(page=440, start_time=None, end_time=None,
             raw_text="Audio Engineering Society AES Abkuerzungsverzeichnis"),
        Unit(page=441, start_time=None, end_time=None,
             raw_text="Audio Engineering Society Standardisierung Norm"),
    ]
    sources = {1: {"source": {"id": 1}, "is_media": False}}
    out = fill_uncited_lines(text, sources, _FakeLoader(units))
    assert "[1, S. 440" in out
    assert "[1, S. 441" in out


def test_clear_winner_still_gets_single_chip():
    # A line that grounds confidently on ONE page must still get exactly one chip.
    text = "- Zotero und Citavi zur Literaturverwaltung.\n"
    units = [
        Unit(page=3, start_time=None, end_time=None, raw_text="ganz anderes thema ohne bezug"),
        Unit(page=15, start_time=None, end_time=None,
             raw_text="literaturverwaltung tools zotero citavi mendeley"),
    ]
    sources = {1: {"source": {"id": 1}, "is_media": False}}
    out = fill_uncited_lines(text, sources, _FakeLoader(units))
    assert "[1, S. 15 |" in out
    assert "[1, S. 3" not in out
    assert out.count("[1, S.") == 1


def test_multi_source_picks_best():
    text = "- Zotero und Citavi Literaturverwaltung.\n"
    weak = [Unit(page=3, start_time=None, end_time=None, raw_text="ganz anderes thema ohne bezug")]
    strong = [Unit(page=15, start_time=None, end_time=None,
                   raw_text="literaturverwaltung tools zotero citavi mendeley")]
    sources = {1: {"source": {"id": 1}, "is_media": False},
               2: {"source": {"id": 2}, "is_media": False}}

    class _Multi:
        def units(self, source, *, is_media):
            return strong if source["id"] == 2 else weak

    out = fill_uncited_lines(text, sources, _Multi())
    assert "[2, S. 15 |" in out  # the strong source wins


def test_media_stem_match_grounds_paraphrased_bullet():
    # Media bullet paraphrases the transcript ("Schneeballsystem" vs spoken
    # "Schneeballprinzip"); stem matching still grounds it to the segment. (PDF
    # stays exact — see test_citation_match stem tests.)
    text = "- Schneeballsystem und Literatur.\n"
    units = [Unit(page=None, start_time=1040.0, end_time=1060.0,
                  raw_text="von einer quelle ausgehend schneeballprinzip weitere literatur finden")]
    sources = {1: {"source": {"id": 1}, "is_media": True}}
    out = fill_uncited_lines(text, sources, _FakeLoader(units))
    assert "[1, 17:20" in out   # 1040s -> 17:20, grounded via stem match
