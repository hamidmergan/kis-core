"""Der Wortschatz-Lückentext: ein Text, eine Aufgabe, keine Ablenker.

Ein Set ist genau EINE Aufgabe. Der Text trägt Platzhalter, die Lösungen hängen
in extras.gaps daran, und die Chips unter dem Text sind die Grundformen. Es gibt
so viele Chips wie Lücken, absichtlich keine Ablenker: wer aus einem
Lernkarten-Set übt, will genau diese Karten üben.

Kein DB- und kein Netzzugriff.
"""

import json
import types

import pytest

from src.features.ai_assistant.tasks.language_training._context import QuelleContext
from src.features.ai_assistant.tasks.language_training._source_cloze import (
    clean_gaps,
    generate_cloze_from_source,
    placeholders,
)


@pytest.fixture
def attributed(monkeypatch):
    """attach_chips_cited greift auf pgvector-Attribution zu und braucht dafuer eine
    Datenbank (DATABASE_URL). Zuordnung ist nicht Gegenstand dieser Tests, deshalb wird
    hier nur der Aufruf durch ein Nichtstun ersetzt, der Erzeuger selbst bleibt unveraendert.
    """
    monkeypatch.setattr(
        "src.features.ai_assistant.tasks.language_training._source_cloze"
        ".attach_chips_cited", lambda items, claims, ctx, **kw: items)


def _ctx():
    return QuelleContext(
        context="[Skript.pdf, S. 12] Die Anlage arbeitet seit gestern wieder.",
        first_label="Skript.pdf",
        multi_label="Skript.pdf",
        source_hint="folgender Quelle",
        source_by_name={"Skript.pdf": {"id": 1, "workspace_id": 7}},
        sections={1: "Skript.pdf"},
        seen_pages_by_source={1: {12}},
    )


def _client(payload):
    """Ein Modell, das genau einmal antwortet. Zählt die Aufrufe mit."""
    calls = []

    def create(model, messages, **kwargs):
        calls.append(messages)
        content = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=content))]
        )

    client = types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
    )
    return client, calls


_GOOD = {
    "title": "Anlage und Filter",
    "instruction": "Setze die Wörter in der passenden Form ein.",
    "example": {"gapped": "Der Techniker ___ die Anlage. (prüfen)", "solved": "prüft"},
    "text": "Die Anlage {{1}} wieder, weil der Techniker den Filter {{2}} hat.",
    "page": 12,
    "gaps": [
        {"base": "arbeiten", "solution": "arbeitet"},
        {"base": "wechseln", "solution": "gewechselt"},
    ],
}


def test_platzhalter_werden_der_reihe_nach_gelesen():
    assert placeholders("a {{1}} b {{2}} c") == [1, 2]
    assert placeholders("ohne Lücke") == []
    assert placeholders("{{2}} kommt vor {{1}}") == [2, 1]


def test_ein_set_ist_genau_eine_aufgabe(attributed):
    client, calls = _client(_GOOD)
    result = generate_cloze_from_source(client, "m", _ctx(), 2)
    assert result is not None
    items, title = result
    assert len(items) == 1
    assert len(calls) == 1, "genau ein Modellaufruf, nie zwei"
    assert title == "Anlage und Filter"


def test_die_aufgabe_traegt_text_loesung_und_grundformen(attributed):
    client, _ = _client(_GOOD)
    items, _ = generate_cloze_from_source(client, "m", _ctx(), 2)
    item = items[0]
    assert "{{1}}" in item["front"] and "{{2}}" in item["front"]
    assert "arbeitet" in item["back"] and "gewechselt" in item["back"]
    assert "{{" not in item["back"], "die Musterlösung hat keine Platzhalter mehr"
    assert [g["base"] for g in item["extras"]["gaps"]] == ["arbeiten", "wechseln"]


def test_anweisung_und_beispiel_haengen_an_der_aufgabe(attributed):
    # Nicht am Satz: der Vorrat traegt Aufgaben und keine Set-Spalten. Stuenden sie
    # in instruction/pattern_*, kaeme ein Text aus dem Vorrat ohne Anweisung an.
    client, _ = _client(_GOOD)
    items, _ = generate_cloze_from_source(client, "m", _ctx(), 2)
    extras = items[0]["extras"]
    assert extras["instruction"].startswith("Setze die Wörter")
    assert extras["example"]["gapped"] == "Der Techniker ___ die Anlage. (prüfen)"
    assert extras["example"]["solved"] == "prüft"


def test_so_viele_chips_wie_luecken(attributed):
    client, _ = _client(_GOOD)
    items, _ = generate_cloze_from_source(client, "m", _ctx(), 2)
    item = items[0]
    assert len(item["extras"]["gaps"]) == len(placeholders(item["front"]))


def test_eine_luecke_ohne_loesung_wird_im_text_gefuellt():
    # Eine unbrauchbare Lücke darf den Text nicht zerreissen. Sie wird eingesetzt
    # und verschwindet aus den Chips, der Text bleibt lesbar.
    kaputt = dict(_GOOD, gaps=[
        {"base": "arbeiten", "solution": "arbeitet"},
        {"base": "wechseln", "solution": "   "},
    ])
    text, gaps = clean_gaps(kaputt["text"], kaputt["gaps"], None)
    assert len(gaps) == 1
    assert placeholders(text) == [1]
    assert "{{2}}" not in text


def test_dieselbe_grundform_kommt_nur_einmal_vor():
    doppelt = dict(_GOOD, gaps=[
        {"base": "arbeiten", "solution": "arbeitet"},
        {"base": "Arbeiten", "solution": "arbeiten"},
    ])
    text, gaps = clean_gaps(doppelt["text"], doppelt["gaps"], None)
    assert len(gaps) == 1, "sonst stünde derselbe Chip zweimal unter dem Text"


def test_bei_lernkarten_kommt_nur_durch_was_auf_einer_karte_steht():
    fremd = dict(_GOOD, gaps=[
        {"base": "arbeiten", "solution": "arbeitet"},
        {"base": "wechseln", "solution": "gewechselt"},
    ])
    text, gaps = clean_gaps(fremd["text"], fremd["gaps"], words=["arbeiten"])
    assert [g["base"] for g in gaps] == ["arbeiten"]


def test_ein_durchlauf_ohne_brauchbare_luecke_gilt_als_misslungen():
    leer = dict(_GOOD, gaps=[
        {"base": "", "solution": ""},
        {"base": "", "solution": ""},
    ])
    client, _ = _client(leer)
    assert generate_cloze_from_source(client, "m", _ctx(), 2) is None


def test_eine_unlesbare_antwort_gilt_als_misslungen():
    client, _ = _client("kein JSON")
    assert generate_cloze_from_source(client, "m", _ctx(), 2) is None


def test_die_kartenliste_steht_im_auftrag_an_das_modell(attributed):
    client, calls = _client(_GOOD)
    generate_cloze_from_source(client, "m", _ctx(), 2, words=["arbeiten", "wechseln"])
    auftrag = "\n".join(m["content"] for m in calls[0])
    assert "arbeiten" in auftrag and "wechseln" in auftrag
