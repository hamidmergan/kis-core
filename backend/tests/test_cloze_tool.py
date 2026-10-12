"""The vocabulary cloze: one text, one exercise, no distractors."""

import json
import types

import pytest

from src.features.ai_assistant.tasks.language_training._context import QuelleContext
from src.features.ai_assistant.tasks.language_training._source_cloze import (
    _cut_gaps,
    clean_gaps,
    generate_cloze_from_source,
    placeholders,
)


@pytest.fixture
def attributed(monkeypatch):
    """The attribution needs a database and is replaced by a no-op here."""
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
    """A model that answers exactly once and counts the calls."""
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
    # One call writes the exercise, a second one only proofreads it.
    assert len(calls) == 2
    assert "proofreader" in calls[1][0]["content"]
    assert title == "Anlage und Filter"


def test_die_aufgabe_traegt_text_loesung_und_grundformen(attributed):
    client, _ = _client(_GOOD)
    items, _ = generate_cloze_from_source(client, "m", _ctx(), 2)
    item = items[0]
    assert "{{1}}" in item["front"] and "{{2}}" in item["front"]
    assert "arbeitet" in item["back"] and "gewechselt" in item["back"]
    assert "{{" not in item["back"], "die Musterlösung hat keine Platzhalter mehr"
    assert [g["base"] for g in item["extras"]["gaps"]] == ["arbeiten", "wechseln"]


def test_die_zitierte_seite_erreicht_die_zuordnung_mit_unterstrich(monkeypatch):
    # Only with an underscore does the first, free stage of the attribution apply.
    empfangen = []

    def aufzeichnen(items, claims, ctx, **kw):
        empfangen.extend(items)
        return items

    monkeypatch.setattr(
        "src.features.ai_assistant.tasks.language_training._source_cloze"
        ".attach_chips_cited", aufzeichnen)
    client, _ = _client(_GOOD)
    generate_cloze_from_source(client, "m", _ctx(), 2)
    assert empfangen[0]["_page"] == 12
    assert "page" not in empfangen[0]


def test_die_anweisung_haengt_an_der_aufgabe(attributed):
    # The instruction lives in extras, otherwise the pool loses it.
    client, _ = _client(_GOOD)
    items, _ = generate_cloze_from_source(client, "m", _ctx(), 2)
    extras = items[0]["extras"]
    assert extras["instruction"].startswith("Setze die Wörter")
    assert "example" not in extras


def test_kein_beispiel_wird_bestellt(attributed):
    # The view dropped the example on 31.08.2026, writing it only cost time.
    client, calls = _client(_GOOD)
    generate_cloze_from_source(client, "m", _ctx(), 2)
    assert "example" not in calls[0][0]["content"].lower()


def test_so_viele_chips_wie_luecken(attributed):
    client, _ = _client(_GOOD)
    items, _ = generate_cloze_from_source(client, "m", _ctx(), 2)
    item = items[0]
    assert len(item["extras"]["gaps"]) == len(placeholders(item["front"]))


def test_eine_luecke_ohne_loesung_wird_im_text_gefuellt():
    # An unusable gap must not tear the text apart.
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


def test_eine_luecke_ohne_platzhalter_im_text_wird_kein_ablenker_chip():
    # A chip without a gap in the text would be a distractor.
    drei = dict(_GOOD,
               text="Die Anlage {{1}} wieder, der Techniker {{2}} den Filter.",
               gaps=[
                   {"base": "arbeiten", "solution": "arbeitet"},
                   {"base": "wechseln", "solution": "gewechselt"},
                   {"base": "prüfen", "solution": "geprüft"},
               ])
    text, gaps = clean_gaps(drei["text"], drei["gaps"], None)
    assert len(gaps) == len(placeholders(text))
    assert len(gaps) == 2


def test_platzhalter_luecke_wird_beim_durchnummerieren_uebersprungen():
    # The numbers have to run without gaps from 1.
    spruenge = dict(_GOOD,
                    text="Die Anlage {{1}} wieder, der Filter wurde {{3}}.",
                    gaps=[
                        {"base": "arbeiten", "solution": "arbeitet"},
                        {"base": "prüfen", "solution": "geprüft"},
                        {"base": "wechseln", "solution": "gewechselt"},
                    ])
    text, gaps = clean_gaps(spruenge["text"], spruenge["gaps"], None)
    assert placeholders(text) == [1, 2]
    assert len(gaps) == 2


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


def test_luecken_als_stringliste_gilt_als_misslungen():
    # Plain strings instead of objects must not crash it.
    kaputt = dict(_GOOD, gaps=["arbeiten", "wechseln"])
    client, _ = _client(kaputt)
    assert generate_cloze_from_source(client, "m", _ctx(), 2) is None


def test_text_ohne_zeichenkette_gilt_als_misslungen():
    # A missing or malformed text must not crash it.
    liste_statt_text = dict(_GOOD, text=["A", "B"])
    client, _ = _client(liste_statt_text)
    assert generate_cloze_from_source(client, "m", _ctx(), 2) is None

    ohne_text = {k: v for k, v in _GOOD.items() if k != "text"}
    client, _ = _client(ohne_text)
    assert generate_cloze_from_source(client, "m", _ctx(), 2) is None


def test_die_schwelle_zaehlt_die_bestellte_menge_nicht_die_rueckgabe():
    # The minimum rate is measured against the ordered count.
    viele = dict(_GOOD,
                text="A {{1}} B {{2}} C {{3}} D {{4}}.",
                gaps=[
                    {"base": "arbeiten", "solution": "arbeitet"},
                    {"base": "wechseln", "solution": "gewechselt"},
                    {"base": "Arbeiten", "solution": "arbeitet"},
                    {"base": "Wechseln", "solution": "gewechselt"},
                ])
    client, _ = _client(viele)
    assert generate_cloze_from_source(client, "m", _ctx(), 10) is None


def test_die_kartenliste_steht_im_auftrag_an_das_modell(attributed):
    client, calls = _client(_GOOD)
    generate_cloze_from_source(client, "m", _ctx(), 2, words=["arbeiten", "wechseln"])
    auftrag = "\n".join(m["content"] for m in calls[0])
    assert "arbeiten" in auftrag and "wechseln" in auftrag


# The model gave the answer away in brackets, the code cleans that up.

def test_klammer_mit_grundform_nach_luecke_wird_entfernt(attributed):
    # The exact bug: the base form stood in brackets behind the gap.
    verraten = dict(_GOOD,
                    text="Man nutzt oft den {{1}} (gemeiner Wert) für Gebäude.",
                    gaps=[{"base": "gemeiner Wert", "solution": "gemeinen Wert"}])
    client, _ = _client(verraten)
    result = generate_cloze_from_source(client, "m", _ctx(), 1)
    assert result is not None
    items, _ = result
    front = items[0]["front"]
    assert "gemeiner Wert" not in front
    assert "{{1}}" in front
    assert len(items[0]["extras"]["gaps"]) == 1


def test_klammer_mit_loesung_nach_luecke_wird_entfernt(attributed):
    # The same faulty shape, only with the inflected form in the bracket.
    verraten = dict(_GOOD,
                    text="Man nutzt oft den {{1}} (gemeinen Wert) für Gebäude.",
                    gaps=[{"base": "gemeiner Wert", "solution": "gemeinen Wert"}])
    client, _ = _client(verraten)
    result = generate_cloze_from_source(client, "m", _ctx(), 1)
    assert result is not None
    items, _ = result
    front = items[0]["front"]
    assert "gemeinen Wert" not in front
    assert "{{1}}" in front


def test_unabhaengige_klammer_nach_luecke_bleibt_stehen(attributed):
    # A bracket unrelated to the gap is prose and stays.
    harmlos = dict(_GOOD,
                   text="Man nutzt oft den {{1}} (siehe Anlage 3) für Gebäude.",
                   gaps=[{"base": "gemeiner Wert", "solution": "gemeinen Wert"}])
    client, _ = _client(harmlos)
    result = generate_cloze_from_source(client, "m", _ctx(), 1)
    assert result is not None
    items, _ = result
    assert "(siehe Anlage 3)" in items[0]["front"]


def test_klammer_fern_von_der_luecke_bleibt_stehen(attributed):
    # Only a bracket directly behind the placeholder counts as suspicious.
    fern = dict(_GOOD,
               text="Der Wert (siehe Anlage 3) wird mit dem {{1}} berechnet.",
               gaps=[{"base": "gemeiner Wert", "solution": "gemeinen Wert"}])
    client, _ = _client(fern)
    result = generate_cloze_from_source(client, "m", _ctx(), 1)
    assert result is not None
    items, _ = result
    front = items[0]["front"]
    assert "(siehe Anlage 3)" in front
    assert "{{1}}" in front


def test_die_formen_mischung_steht_als_zahl_im_auftrag():
    # A statement of intent does not steer this model, a number does.
    client, calls = _client(_GOOD)
    generate_cloze_from_source(client, "m", _ctx(), 10)
    auftrag = calls[0][0]["content"]
    assert "At least 3 of the 10 gaps" in auftrag


def test_bei_einer_einzigen_luecke_fehlt_die_wortart_mischung():
    # With exactly one gap the mix requirement would be impossible.
    client, calls = _client(_GOOD)
    generate_cloze_from_source(client, "m", _ctx(), 1)
    auftrag = calls[0][0]["content"]
    assert "must not all be the same part of speech" not in auftrag
    assert "At least 1 of the 1 gaps" in auftrag


def test_die_formen_mischung_nennt_die_erzwingenden_satzstellen():
    # The number alone forces nothing, the prompt has to name the position.
    client, calls = _client(_GOOD)
    generate_cloze_from_source(client, "m", _ctx(), 10)
    auftrag = calls[0][0]["content"]
    assert "agree with its subject" in auftrag
    assert "adjective" in auftrag and "ending" in auftrag
    assert "plural" in auftrag
    assert "grammatical case" in auftrag
    assert "does NOT count towards this number" in auftrag
    assert "must not all be the same part of speech" in auftrag


def test_cut_gaps_schneidet_in_textreihenfolge():
    text, gaps = _cut_gaps(
        "Man muss sich einleben und Fortschritte machen.",
        [{"base": "Fortschritt", "solution": "Fortschritte"},
         {"base": "einleben", "solution": "einleben"}],
    )
    assert text == "Man muss sich {{1}} und {{2}} machen."
    assert [g["solution"] for g in gaps] == ["einleben", "Fortschritte"]


def test_cut_gaps_verwirft_mehrdeutige_und_fehlende():
    text, gaps = _cut_gaps(
        "Sie lernt viel und lernt gern. Das Ziel ist klar.",
        [{"base": "lernen", "solution": "lernt"},
         {"base": "Ziel", "solution": "Ziel"},
         {"base": "Plan", "solution": "Plan"}],
    )
    assert text == "Sie lernt viel und lernt gern. Das {{1}} ist klar."
    assert [g["solution"] for g in gaps] == ["Ziel"]


def test_cut_gaps_nur_ganze_woerter():
    text, gaps = _cut_gaps("Die Sprachprüfung ist schwer.", [{"base": "Prüfung", "solution": "Prüfung"}])
    assert text == "Die Sprachprüfung ist schwer."
    assert gaps == []
