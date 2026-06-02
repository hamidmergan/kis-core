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
