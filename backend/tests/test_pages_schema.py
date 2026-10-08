"""The page schema cuts every page to its limits and the draft is built from plan and blocks."""

from src.features.pages import pipeline as pl
from src.features.pages import schema
from src.features.summary.models import Outline, Section
from src.limits import PAGES_MAX_SECTIONS, PAGES_MAX_SHORT_CHARS, PAGES_MAX_TABLE_ROWS
from src.services.source_reading import Source


def _page(*sections, **extra):
    return {"sections": list(sections), **extra}


def test_unknown_kinds_and_html_never_survive():
    page = schema.clean_page(_page({"id": "a", "title": "<b>T</b>", "blocks": [
        {"kind": "script", "text": "x"}, {"kind": "bullets", "items": ["eins", "", None, {"x": 1}]}]}))
    blocks = page["sections"][0]["blocks"]
    assert blocks == [{"kind": "bullets", "items": ["eins"]}]
    # Text stays text, the frontend escapes it, nothing here turns it into markup.
    assert page["sections"][0]["title"] == "<b>T</b>"


def test_limits_cut_sections_tables_and_text():
    viele = [{"title": f"S{i}", "blocks": [{"kind": "bullets", "items": ["x"]}]} for i in range(40)]
    page = schema.clean_page(_page(*viele))
    assert len(page["sections"]) == PAGES_MAX_SECTIONS
    zeilen = [[str(i), "a", "b"] for i in range(30)]
    t = schema.clean_block({"kind": "table", "header": ["", "A", "B"], "rows": zeilen})
    assert len(t["rows"]) == PAGES_MAX_TABLE_ROWS
    lang = schema.clean_page(_page({"title": "Wort " * 100, "blocks": []}))
    assert len(lang["sections"][0]["title"]) <= PAGES_MAX_SHORT_CHARS


def test_chart_needs_matching_numbers():
    gut = schema.clean_block({"kind": "chart", "chart_type": "line", "categories": ["1", "2", "3"],
                              "series": [{"name": "a", "values": [1, "2,5", 3]}]})
    assert gut["series"][0]["values"] == [1.0, 2.5, 3.0]
    assert schema.clean_block({"kind": "chart", "categories": ["1", "2", "3"],
                               "series": [{"values": [1, 2]}]}) is None


def test_images_only_by_their_own_names():
    assert schema.clean_block({"kind": "image", "src": "../../etc/passwd"}) is None
    assert schema.clean_block({"kind": "image", "src": "img_0.webp"})["src"] == "img_0.webp"


def test_hidden_sections_stay_with_the_owner():
    page = schema.clean_page(_page(
        {"id": "a", "title": "Sichtbar", "blocks": [{"kind": "image", "src": "img_0.webp"}]},
        {"id": "b", "title": "Versteckt", "hidden": True, "blocks": [{"kind": "image", "src": "img_1.webp"}]}))
    sicht = schema.for_viewers(page)
    assert [s["id"] for s in sicht["sections"]] == ["a"]
    assert schema.images_of(page) == {"img_0.webp"}


def test_duplicate_section_ids_are_renamed():
    page = schema.clean_page(_page({"id": "a", "title": "x"}, {"id": "a", "title": "y"}))
    ids = [s["id"] for s in page["sections"]]
    assert len(set(ids)) == 2


def test_word_cloud_counts_the_material():
    woerter = pl.word_cloud(["Gerade", "gerade", "Residuum", "fehlt"],
                            "Die Gerade, die Gerade und ein Residuum.")
    assert woerter == [["Gerade", 2], ["Residuum", 1]]


def test_draft_builds_title_gist_map_sections_and_cloud():
    plan = Outline(title="Lineare Regression", intro="Es geht um Geraden. Sie sagen voraus.",
                   sections=[Section(title=f"Teil {i}") for i in range(4)])
    stoff = " ".join(["Steigung Achsenabschnitt Residuum Korrelation Varianz Modell"] * 3)
    bloecke = {i: {"lead": "Lead", "map_label": f"T{i}",
                   "blocks": [{"kind": "bullets", "items": ["a", "b"]}],
                   "keywords": ["Steigung", "Achsenabschnitt", "Residuum", "Korrelation", "Varianz",
                                "Modell"][i:i + 3]}
               for i in range(4)}
    frame = {"lead": "Kurz", "gist": ["Eins.", "Zwei."], "key": {"key": "y = a + bx", "text": "t"},
             "hero_prompt": "a desk", "section_image": {"section_index": 1, "prompt": "a lamp"}}
    quelle = Source(dateiname="Skript.pdf", fassung="x", text=stoff, stuecke=[], seiten=1)
    seite = pl.draft(plan, bloecke, frame, sources=[quelle], language="German")
    ids = [s["id"] for s in seite["sections"]]
    assert ids == ["top", "gist", "map", "s1", "s2", "s3", "s4", "words"]
    assert seite["sections"][0]["blocks"][0]["src"] == pl.HERO_IMAGE
    assert seite["sections"][4]["blocks"][0]["src"] == pl.SECTION_IMAGE
    assert seite["names"] == "Skript"
    fertig = pl.finish(schema.clean_page(seite), names="Skript", today=__import__("datetime").date(2026, 10, 8))
    assert "08.10.2026" in fertig["sections"][0]["meta"]
