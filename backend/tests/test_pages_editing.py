"""Sections the owner adds as a grid of fields, and a page carried into another language."""

import asyncio
import json
from types import SimpleNamespace

from src.features.pages import schema
from src.features.pages import translate as tr
from src.limits import PAGES_MAX_ITEM_CHARS, PAGES_MAX_LONG_CHARS


def _page(*sections, **extra):
    return {"sections": list(sections), **extra}


def test_layout_keeps_every_field_in_its_place():
    page = schema.clean_page(_page({"id": "n1", "title": "Neu", "layout": "3", "blocks": [
        {"kind": "empty"}, {"kind": "bullets", "items": ["a"]}, {"kind": "script"}, {"kind": "text", "text": "x"}]}))
    s = page["sections"][0]
    assert s["layout"] == "3"
    assert [b["kind"] for b in s["blocks"]] == ["empty", "bullets", "empty"]


def test_layout_pads_missing_fields_and_unknown_layout_is_dropped():
    page = schema.clean_page(_page(
        {"id": "n1", "title": "Neu", "layout": "4", "blocks": [{"kind": "text", "text": "x"}]},
        {"id": "n2", "title": "Alt", "layout": "9", "blocks": [{"kind": "empty"}, {"kind": "text", "text": "y"}]}))
    assert [b["kind"] for b in page["sections"][0]["blocks"]] == ["text", "empty", "empty", "empty"]
    assert "layout" not in page["sections"][1]
    assert page["sections"][1]["blocks"] == [{"kind": "text", "text": "y"}]


def test_an_untouched_new_section_without_text_goes():
    page = schema.clean_page(_page({"id": "n1", "title": "", "layout": "2", "blocks": []},
                                   {"id": "s1", "title": "Bleibt", "blocks": []}))
    assert [s["id"] for s in page["sections"]] == ["s1"]


def test_languages_and_easy_survive_cleaning():
    assert schema.clean_page(_page({"title": "T"}, lang="uk"))["lang"] == "uk"
    assert schema.clean_page(_page({"title": "T"}, lang="xx"))["lang"] == "de"
    assert schema.clean_page(_page({"title": "T"}, lang="de", easy=True))["easy"] is True
    assert "easy" not in schema.clean_page(_page({"title": "T"}, lang="en", easy=True))


SAMPLE = schema.clean_page(_page(
    {"id": "top", "hero": True, "title": "Regression", "lead": "Ein Überblick.", "meta": "Erstellt mit KI",
     "blocks": [{"kind": "image", "src": "img_0.webp", "alt": "Bild", "prompt": "flat", "caption": ""}]},
    {"id": "s1", "title": "Gerade", "lead": "", "blocks": [
        {"kind": "text", "text": "Die Gerade passt."},
        {"kind": "chart", "chart_type": "bar", "caption": "Werte", "x_label": "Jahr", "y_label": "",
         "categories": ["2020", "2021"], "series": [{"name": "", "values": [1, 2]}]},
        {"kind": "highlight", "key": "y = a + bx", "text": "Die Formel."}]},
    {"id": "words", "title": "Wörter", "lead": "", "blocks": [
        {"kind": "wordcloud", "caption": "", "words": [["Gerade", 3], ["Wert", 2], ["Fehler", 1]]}]},
    lang="de"))


def test_texts_leave_pictures_numbers_and_ids_alone():
    gefunden = dict(tr.texts(SAMPLE))
    werte = set(gefunden.values())
    assert "Regression" in werte and "Die Gerade passt." in werte and "Gerade" in werte
    assert "img_0.webp" not in werte and "flat" not in werte and "s1" not in werte and "bar" not in werte
    assert not any(isinstance(v, (int, float)) for v in werte)


def test_limits_follow_the_place_of_a_text():
    texte = dict(tr.texts(SAMPLE))
    by_text = {v: k for k, v in texte.items()}
    assert tr._limit(SAMPLE, by_text["Die Gerade passt."]) == PAGES_MAX_LONG_CHARS
    assert tr._limit(SAMPLE, by_text["Die Formel."]) == PAGES_MAX_ITEM_CHARS
    assert tr._limit(SAMPLE, by_text["2020"]) == schema.CHART_LABEL_CHARS
    assert tr._limit(SAMPLE, by_text["Fehler"]) == schema.MAP_LABEL_CHARS


class _FakeCaller:
    """Answers like a model that drops one key in a batch and gets it right alone."""

    def __init__(self):
        self.calls = 0

    async def create(self, **kwargs):
        self.calls += 1
        daten = json.loads(kwargs["messages"][1]["content"].split("\n\n", 1)[1])
        antwort = {k: "EN " + v["text"] for k, v in daten.items()}
        if len(daten) > 1:
            antwort.pop("1")
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(antwort)))])


def test_translate_puts_every_text_back_and_asks_again_for_a_dropped_one():
    caller = _FakeCaller()
    neu = asyncio.run(tr.translate(caller, SAMPLE, "en"))
    assert neu["lang"] == "en" and "easy" not in neu
    assert neu["sections"][0]["title"] == "EN Regression"
    assert neu["sections"][1]["blocks"][0]["text"] == "EN Die Gerade passt."
    assert neu["sections"][1]["blocks"][1]["series"][0]["values"] == [1.0, 2.0]
    assert neu["sections"][0]["blocks"][0]["src"] == "img_0.webp"
    assert [s["id"] for s in neu["sections"]] == [s["id"] for s in SAMPLE["sections"]]
    # The same texts at the same places, nothing left in German.
    assert all(v.startswith("EN ") for _, v in tr.texts(neu))


def test_easy_language_is_german_with_its_flag():
    neu = asyncio.run(tr.translate(_FakeCaller(), SAMPLE, "easy"))
    assert neu["lang"] == "de" and neu["easy"] is True


def test_a_save_without_change_keeps_the_stamp():
    from src.tasks.pages_tasks import stamp

    gespeichert = {**SAMPLE, "saved_at": "2026-10-08T10:00:00Z"}
    assert stamp(gespeichert) == stamp({**SAMPLE, "saved_at": "2026-10-09T10:00:00Z"})
    geaendert = json.loads(json.dumps(SAMPLE))
    geaendert["sections"][1]["title"] = "Andere"
    assert stamp(geaendert) != stamp(SAMPLE)


def test_a_section_hidden_in_the_page_stays_hidden_in_every_language(monkeypatch):
    from src.tasks import pages_tasks as pt

    seite = json.loads(json.dumps(SAMPLE))
    seite["sections"][1]["hidden"] = True
    variante = json.loads(json.dumps(SAMPLE))
    variante["lang"] = "en"
    variante["sections"][1]["blocks"].append(
        {"kind": "image", "src": "img_7.webp", "alt": "", "prompt": "p", "caption": ""})
    monkeypatch.setattr(pt, "readable", lambda *a: [{"key": "de", "label": "Deutsch"}, {"key": "en", "label": "English"}])
    monkeypatch.setattr(pt, "load_variant", lambda *a: json.loads(json.dumps(variante)))

    gezeigt = schema.for_viewers(pt.in_language(1, "j", seite, "en"))
    assert "s1" not in [s["id"] for s in gezeigt["sections"]]
    assert "img_7.webp" not in pt.viewer_images(1, "j", seite)
    assert "img_0.webp" in pt.viewer_images(1, "j", seite)
