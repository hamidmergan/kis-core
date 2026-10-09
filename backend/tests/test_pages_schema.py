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
    frame = {"lead": "Kurz", "gist": ["Eins.", "Zwei."], "formula": {"key": "y = a + bx", "text": "t"},
             "design": "magazine",
             "hero_prompt": "a desk", "section_image": {"section_index": 1, "prompt": "a lamp"}}
    quelle = Source(dateiname="Skript.pdf", fassung="x", text=stoff, stuecke=[], seiten=1)
    seite = pl.draft(plan, bloecke, frame, sources=[quelle], language="German")
    ids = [s["id"] for s in seite["sections"]]
    assert ids == [pl.COVER_ID, "top", "gist", "map", "s1", "s2", "s3", "s4", "words"]
    assert seite["sections"][0]["blocks"][0]["src"] == pl.HERO_IMAGE
    # One picture per page, at the top, an older frame's section picture is left out.
    assert [b["src"] for x in seite["sections"] for b in x["blocks"] if b["kind"] == "image"] == [pl.HERO_IMAGE]
    assert seite["footer"] == ""
    fertig = pl.finish(schema.clean_page(seite), today=__import__("datetime").date(2026, 10, 8))
    # The page names no source, that stays with the owner behind the info icon.
    assert fertig["sections"][1]["meta"].startswith("Erstellt mit KI am 08.10.2026, etwa ")
    assert "Skript" not in fertig["sections"][1]["meta"]


def test_long_highlight_key_becomes_text_and_dashes_go():
    b = schema.clean_block({"kind": "highlight", "key": "Tägliche Höchstarbeitszeit 8 Stunden, Verlängerung bis 10 Stunden", "text": "Gilt immer"})
    assert b["key"] == "" and b["text"].startswith("Tägliche Höchstarbeitszeit")
    assert schema.text("Arbeitszeitgesetz – Überblick", 120) == "Arbeitszeitgesetz: Überblick"
    assert schema.text("lang – aber gut", 120) == "lang, aber gut"
    assert pl._short_title("Arbeitszeitgesetz: Überblick für Studierende") == "Arbeitszeitgesetz"


def test_cards_once_no_blue_box_and_the_design_is_kept():
    plan = Outline(title="T", intro="I.", sections=[Section(title=f"S{i}") for i in range(4)])
    karten = {"kind": "cards", "cards": [{"title": "A", "text": "a"}, {"title": "B", "text": "b"}]}
    hl = {"kind": "highlight", "key": "y = a + bx", "text": "Gerade"}
    bloecke = {i: {"lead": "", "blocks": [dict(karten), dict(hl)], "keywords": []} for i in range(4)}
    seite = pl.draft(plan, bloecke, {"formula": {"key": "Risikowert", "text": "W mal A"}, "design": "guide",
                                     "hero_prompt": "a desk"},
                     sources=[Source(dateiname="a.pdf", fassung="x", text="t", stuecke=[], seiten=1)],
                     language="German")
    arten = [b["kind"] for s in seite["sections"] for b in s["blocks"]]
    assert "highlight" not in arten
    assert arten.count("cards") == 1 and arten.count("formula") == 1
    # A frame formula without a sign is a term, it becomes a definition.
    assert seite["sections"][2]["blocks"][1] == {"kind": "definitions", "items": [{"term": "Risikowert", "text": "W mal A"}]}
    assert seite["design"] == "guide"
    # Every page opens with its picture as a section of its own above the title.
    assert seite["sections"][0]["id"] == pl.COVER_ID
    assert [b["src"] for b in seite["sections"][0]["blocks"]] == [pl.HERO_IMAGE]
    assert seite["sections"][1]["hero"] is True and seite["sections"][1]["blocks"] == []
    assert schema.clean_block({"kind": "text", "text": "Ein Satz."}) == {"kind": "text", "text": "Ein Satz."}


def test_own_picture_style_replaces_the_default():
    assert pl.image_prompt("a desk", "Watercolour, soft greens.").startswith("Watercolour, soft greens. Subject: a desk")
    assert pl.image_prompt("a desk").startswith(pl.default_image_style())


def test_page_as_text_keeps_sections_and_spells_out_charts():
    from src.features.pages import text as pt
    page = schema.clean_page(_page(
        {"id": "top", "hero": True, "title": "T", "lead": "L", "meta": "Erstellt mit KI"},
        {"id": "s1", "title": "Messwerte", "blocks": [{"kind": "chart", "chart_type": "line", "caption": "Punkte",
            "categories": ["2", "4", "6"], "series": [{"name": "Gemessen", "values": [18, 30, 32.5]}]}]},
        {"id": "s2", "title": "Versteckt", "hidden": True, "blocks": [{"kind": "text", "text": "geheim"}]},
        {"id": "map", "title": "Karte", "blocks": []}))
    teile = pt.parts(page)
    assert [p.anchor for p in teile] == ["top", "s1"]
    assert "Gemessen: 2: 18, 4: 30, 6: 32,5" in teile[1].text
    assert "geheim" not in pt.as_text(page)


def test_a_page_gets_its_picture_from_the_title_when_the_frame_names_none():
    plan = Outline(title="Arbeitszeitgesetz", intro="Regeln.", sections=[Section(title="Pausen")])
    bloecke = {0: {"lead": "", "blocks": [{"kind": "text", "text": "Nach sechs Stunden Pause."}], "keywords": []}}
    quelle = Source(dateiname="AZG.pdf", fassung="x", text="Pause", stuecke=[], seiten=1)
    seite = pl.draft(plan, bloecke, {"design": "chapters", "hero_prompt": ""}, sources=[quelle], language="German")
    bild = seite["sections"][0]["blocks"][0]
    assert seite["sections"][0]["id"] == pl.COVER_ID
    assert bild["src"] == pl.HERO_IMAGE and "Arbeitszeitgesetz" in bild["prompt"]
    assert seite["sections"][1]["hero"] is True and seite["sections"][1]["blocks"] == []


def test_new_kinds_are_cleaned_to_their_shape():
    c = schema.clean_block
    assert c({"kind": "cycle", "center": "PDCA", "steps": [{"title": "Plan"}, {"title": "Do"}]})["kind"] == "steps"
    assert c({"kind": "timeline", "events": [{"date": "1957", "title": "CPM"}, {"title": "ohne Datum"}]}) is None
    v = c({"kind": "versus", "tone": "boese", "a": {"title": "A", "items": ["x"]}, "b": {"title": "B", "items": ["y"]}})
    assert v["tone"] == "neutral"
    m = c({"kind": "matrix", "x": "Interesse", "y": "Einfluss", "points": [{"label": "P", "x": 3, "y": "0,5"}],
           "cells": [{"pos": q, "title": q} for q in ("br", "tl", "tr", "bl")]})
    assert [x["pos"] for x in m["cells"]] == ["tl", "tr", "bl", "br"] and m["points"] == [{"label": "P", "x": 1.0, "y": 0.5}]
    s = c({"kind": "scale", "left": "a", "right": "b", "items": [{"label": "y", "pos": 0.9}, {"label": "x", "pos": 0.1}]})
    assert [x["label"] for x in s["items"]] == ["x", "y"]
    assert c({"kind": "formula", "key": "E = m c²", "text": "Energie"})["kind"] == "formula"
    assert c({"kind": "example", "title": "T", "result": "R"}) is None
    assert c({"kind": "chart", "chart_type": "pie", "categories": ["a", "b"],
              "series": [{"values": [1, 2]}, {"values": [3, 4]}]})["series"] == [{"name": "", "values": [1.0, 2.0]}]


def test_bare_chapter_numbers_are_cut_years_and_formulas_stay():
    weg = pl.drop_citations
    assert weg("Es gibt 620 Sitzplätze (2.1).", set()) == "Es gibt 620 Sitzplätze."
    assert weg("Zwei Drittel aus Landesmitteln (1)", set()) == "Zwei Drittel aus Landesmitteln"
    assert weg("Das Manifest (2001) gilt.", set()) == "Das Manifest (2001) gilt."
    assert weg("Der Wert (n = 30) reicht.", set()) == "Der Wert (n = 30) reicht."


def test_prose_comes_first_and_one_block_shows_it():
    text, zeigt = pl._prose_first([
        {"kind": "steps", "steps": [{"title": "A", "text": "a"}]},
        {"kind": "text", "text": "Erster Satz. Zweiter Satz."},
        {"kind": "table", "header": ["", "x"], "rows": [["a", "b"]]},
        {"kind": "text", "text": "Dritter Satz."},
    ])
    assert text == "Erster Satz. Zweiter Satz. Dritter Satz."
    assert [b["kind"] for b in zeigt] == ["steps"]
    assert pl._sentences("Eins ist kurz. Zwei ist auch kurz. Drei passt nicht mehr.", 40) == "Eins ist kurz. Zwei ist auch kurz."


def test_a_formula_stands_once():
    gist = [{"kind": "formula", "key": "E = (O + 4M + P) / 6", "text": "a"}]
    abschnitt = [{"kind": "text", "text": "T."}, {"kind": "formula", "key": "E=(O+4M+P)/6", "text": "b"}]
    pl._once([gist, abschnitt])
    assert [b["kind"] for b in abschnitt] == ["text"]
