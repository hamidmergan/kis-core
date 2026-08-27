"""The hint is produced in the same call as the exercise and lives in extras."""

import json
import types

from src.features.ai_assistant.repository import exercise_pool
from src.features.ai_assistant.tasks.language_training import _source_cards as cards_mod
from src.features.ai_assistant.tasks.language_training import _source_mc as mc_mod
from src.features.ai_assistant.tasks.language_training._hint import attach_hint


def _make_client(content):
    calls = []

    def create(model, messages, **kwargs):
        calls.append(messages)
        message = types.SimpleNamespace(content=content)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])

    return types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
    ), calls


def _ctx():
    return types.SimpleNamespace(source_hint="Quelle", context="ctx", multi_label="T")


# --- storage in extras -------------------------------------------------------

def test_tipp_landet_in_extras():
    item = {"front": "F", "back": "B"}
    attach_hint(item, {"tip": "  Denk an die Waage.  "})
    assert item["extras"] == {"tip": "Denk an die Waage."}


def test_ohne_tipp_bleibt_extras_leer():
    """Without a hint the field stays out, the view falls back to the chat."""
    for roh in ({}, {"tip": ""}, {"tip": "   "}, {"tip": None}, {"tip": 7}):
        item = {"front": "F", "back": "B"}
        attach_hint(item, roh)
        assert "extras" not in item


def test_tipp_verdraengt_vorhandene_extras_nicht():
    """The grammar exercise puts its pattern pair in the same column."""
    item = {"front": "F", "back": "B", "extras": {"pattern_front": "P"}}
    attach_hint(item, {"tip": "Schau auf die Endung."})
    assert item["extras"] == {"pattern_front": "P", "tip": "Schau auf die Endung."}


def test_extras_laeuft_durch_den_vorrat():
    """The hint needs no column of its own, the pool already carries extras."""
    assert "extras" in exercise_pool._ITEM_FIELDS
    assert "extras" in exercise_pool._JSON_FIELDS


# --- Quiz --------------------------------------------------------------------

def test_quiz_nimmt_den_tipp_aus_derselben_antwort(monkeypatch):
    monkeypatch.setattr(mc_mod, "_attach_by_kind", lambda *a, **k: None)
    content = json.dumps({"title": "T", "exercises": [
        {"question": "Was ist X?", "options": ["a", "b", "c", "d"], "correct_idx": 1,
         "tip": "Denk an das Beispiel der falsch kalibrierten Waage."},
        {"sentence": "Der Prozess der ___ senkt den Druck.",
         "options": ["a", "b", "c", "d"], "correct_idx": 2, "tip": "Schau auf Seite 3."},
        {"statement": "Die Anlage arbeitet bei Frost weniger wirtschaftlich.",
         "answer": True, "tip": "Vergleiche Sommer und Winter."},
    ]})
    client, calls = _make_client(content)
    items, _ = mc_mod.generate_mc_from_source(client, "m", _ctx(), 3, locale="de")
    assert len(calls) == 1, "Der Tipp darf keinen zweiten Aufruf kosten"
    assert [i["extras"]["tip"] for i in items] == [
        "Denk an das Beispiel der falsch kalibrierten Waage.",
        "Schau auf Seite 3.",
        "Vergleiche Sommer und Winter.",
    ]


def test_quiz_ohne_tipp_bleibt_eine_gueltige_aufgabe(monkeypatch):
    """A missing hint does not break the exercise."""
    monkeypatch.setattr(mc_mod, "_attach_by_kind", lambda *a, **k: None)
    content = json.dumps({"title": "T", "exercises": [
        {"question": "Was ist X?", "options": ["a", "b", "c", "d"], "correct_idx": 1},
    ]})
    client, _ = _make_client(content)
    items, _ = mc_mod.generate_mc_from_source(client, "m", _ctx(), 1, locale="de")
    assert items[0]["front"] == "Was ist X?"
    assert "extras" not in items[0]


def test_quiz_prompt_bestellt_den_tipp():
    prompt = mc_mod._build_prompt(3, "German")
    assert '"tip"' in prompt
    # The ban stands as a counter-example, not as a statement of intent.
    assert "GOOD:" in prompt and "BAD:" in prompt
    assert "{language}" not in prompt, "Platzhalter muss ersetzt sein"


# --- Karteikarten ------------------------------------------------------------

def test_karteikarten_nehmen_den_tipp_aus_derselben_antwort(monkeypatch):
    monkeypatch.setattr(cards_mod, "attach_chips", lambda *a, **k: None)
    content = json.dumps({"title": "T", "cards": [
        {"question": "Warum kühlt es ab?", "answer": "Weil die Luft sich ausdehnt.",
         "tip": "Denk an den Versuch mit der Pumpe."},
        {"question": "Und dann?", "answer": "Dann steigt der Druck."},
    ]})
    client, calls = _make_client(content)
    items, _ = cards_mod.generate_cards_from_source(client, "m", _ctx(), 2)
    assert len(calls) == 1, "Der Tipp darf keinen zweiten Aufruf kosten"
    assert items[0]["extras"] == {"tip": "Denk an den Versuch mit der Pumpe."}
    assert "extras" not in items[1]
