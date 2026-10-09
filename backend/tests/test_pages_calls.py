"""A page costs few model calls: the frame rides on the plan, repairs and translations go in bulk."""
import asyncio
import json
from types import SimpleNamespace

from src.features.pages import pipeline as pl
from src.features.pages import translate as tr
from src.features.pages import writing as pw
from src.features.summary import writing as sw
from src.features.summary.models import Outline, Section
from src.services import text_map as tm
from src.services.source_reading import from_text

_TEXT = " ".join(f"Satz {i} erklärt den Gegenstand der Vorlesung ausführlich und genau." for i in range(60))


class _Store:
    def __init__(self):
        self.blocks: dict[int, dict] = {}

    def progress(self, *a, **k):
        pass

    def load_blocks(self):
        return dict(self.blocks)

    def save_blocks(self, i, data):
        self.blocks[i] = data


def _plan(n: int) -> Outline:
    return Outline(title="T", intro="I", sections=[
        Section(title=f"Abschnitt {i}", scope="s", stellen=[1]) for i in range(n)])


def _block(i: int, saetze: int = 3) -> dict:
    text = " ".join(f"Satz {k} zu Abschnitt {i}." for k in range(saetze))
    return {"lead": "l", "map_label": "m", "keywords": [],
            "blocks": [{"kind": "text", "text": text}]}


def _run(plan, monkeypatch, antworten, prosa=None):
    """Runs the block stage with scripted answers, returns the calls it made."""
    calls = []

    async def write_blocks(caller, *, indices, **kw):
        calls.append(("blocks", list(indices)))
        return antworten(list(indices))

    async def write_sections(caller, *, group, **kw):
        calls.append(("prosa", [s.title for s in group]))
        return prosa(group) if prosa else ["Ein Satz. Noch ein Satz. Und ein dritter."] * len(group)

    monkeypatch.setattr(pl, "write_blocks", write_blocks)
    monkeypatch.setattr(pl.summary_writing, "write_sections", write_sections)
    karte = tm.Karte([from_text("a.txt", _TEXT)])
    store = _Store()
    caller = SimpleNamespace(window_tokens=0)
    fertig = asyncio.run(pl._blocks(caller, language="German", plan=plan, karte=karte, store=store,
                                    should_stop=None, instructions=""))
    return fertig, calls


def test_mehrere_abschnitte_teilen_sich_einen_aufruf(monkeypatch):
    fertig, calls = _run(_plan(8), monkeypatch, lambda idx: [_block(i) for i in idx])
    assert len(fertig) == 8
    assert [c for c in calls if c[0] == "blocks"] == [("blocks", [0, 1, 2, 3, 4]), ("blocks", [5, 6, 7])]


def test_fehlende_abschnitte_kommen_in_einem_aufruf(monkeypatch):
    erster = {"n": 0}

    def antworten(idx):
        erster["n"] += 1
        # The first calls drop every odd section, the repair call delivers them all.
        return [_block(i) if (i % 2 == 0 or erster["n"] > 2) else None for i in idx]

    fertig, calls = _run(_plan(8), monkeypatch, antworten)
    assert len(fertig) == 8
    assert calls[-1] == ("blocks", [1, 3, 5, 7])
    assert len(calls) == 3


def test_was_dann_noch_fehlt_wird_text_in_einem_aufruf(monkeypatch):
    fertig, calls = _run(_plan(4), monkeypatch, lambda idx: [None for _ in idx])
    assert len(fertig) == 4
    assert [c[0] for c in calls] == ["blocks", "blocks", "prosa"]
    assert all(fertig[i]["blocks"] for i in range(4))


def test_zu_kurzer_text_fuer_alle_in_einem_aufruf(monkeypatch):
    fertig, calls = _run(_plan(4), monkeypatch,
                         lambda idx: [_block(i, saetze=1 if i in (1, 2) else 3) for i in idx])
    assert calls[-1] == ("prosa", ["Abschnitt 1", "Abschnitt 2"])
    assert len(calls) == 2
    assert fertig[1]["blocks"][0]["text"].startswith("Ein Satz.")


def test_rahmen_kommt_aus_der_gliederung():
    schema = sw.outline_schema(pw.FRAME_FIELDS)["json_schema"]["schema"]
    assert {"lead", "gist", "hero_prompt"} <= set(schema["required"])
    assert "lead" not in sw.OUTLINE_SCHEMA["json_schema"]["schema"]["properties"]

    antwort = json.dumps({
        "title": "Titel", "intro": "Intro.", "documents": [],
        "sections": [{"section_index": i, "title": f"A{i}", "description": "d", "refs": [], "start": ""}
                     for i in range(4)],
        "lead": "Worum es geht.", "gist": ["Eins.", "Zwei.", "Drei."],
        "formula": {"key": "", "text": ""}, "design": "chapters",
        "hero_prompt": "a calm scene", "hero_alt": "Ein Bild.",
    })
    plan = sw.parse_outline(antwort, extra=list(pw.FRAME_FIELDS))
    frame = pw.frame_from_plan(plan.extra)
    assert frame["lead"] == "Worum es geht."
    assert frame["formula"] is None
    assert pw.frame_from_plan({}) == {}


def test_uebersetzung_packt_abschnitte_zusammen():
    items = [(("sections", s, "blocks", 0, "text"), "x" * 500) for s in range(10) for _ in range(2)]
    stapel = tr._batches(items)
    assert len(stapel) == 2
    # A section never splits between two calls.
    for b in stapel:
        assert len({p[1] for p, _ in b}) * 2 == len(b)


def test_vergessene_texte_gehen_gesammelt_nochmal(monkeypatch):
    gefragt = []

    async def ask(caller, system, page, batch):
        gefragt.append(len(batch))
        if len(gefragt) == 1:
            return {str(i): "übersetzt" for i in range(1, len(batch) + 1) if i % 3}
        return {str(i): "übersetzt" for i in range(1, len(batch) + 1)}

    monkeypatch.setattr(tr, "_ask", ask)
    page = {"lang": "de", "sections": [{"id": f"s{i}", "title": f"Titel {i}", "lead": "", "blocks": [
        {"kind": "text", "text": f"Text {i}"}]} for i in range(6)]}
    monkeypatch.setattr(tr.schema, "clean_page", lambda p: p)
    neu = asyncio.run(tr.translate(None, page, "en"))
    assert len(gefragt) == 2
    assert all(s["title"] == "übersetzt" for s in neu["sections"])


def test_antwort_in_der_form_der_anfrage_zaehlt(monkeypatch):
    async def create(**kw):
        inhalt = '```json\n{"1": {"text": "Hello", "max_chars": 40}, "2": "World"}\n```'
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=inhalt))])

    page = {"sections": [{"title": "Hallo", "lead": "Welt", "blocks": []}]}
    caller = SimpleNamespace(create=create)
    antwort = asyncio.run(tr._ask(caller, "s", page, [(("sections", 0, "title"), "Hallo"),
                                                       (("sections", 0, "lead"), "Welt")]))
    assert antwort == {"1": "Hello", "2": "World"}
