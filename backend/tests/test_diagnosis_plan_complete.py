"""Jede Zeile im Fragen-Plan muss fertig sein, sonst wird nicht gespeichert.

Frueher war eine halbe Zeile erlaubt: das Modell hat die Frage dann waehrend des
Tests erzeugt. Diesen Weg gibt es nicht mehr, also darf eine halbe Zeile gar nicht
erst in die Datenbank. Geprueft wird beim Speichern, und die Meldung nennt die
Zeilennummer, damit der Admin nicht suchen muss.
"""

import json

from src.services.aia_diagnosis_chat import (
    CHOICE_TYPE,
    DEFAULT_GERMAN_QUESTION_PLAN,
    FREE_TEXT_TYPE,
    first_incomplete_question,
)


# Der Speicher-Endpunkt prueft jedes Feld gegen die Rechte des Aufrufers.
# Ein Administrator hat alle, also aendert das an diesen Tests nichts.
_ADMIN = {"role": "admin"}

def _raw(*items) -> str:
    return json.dumps(list(items))


CHOICE = {
    "type": CHOICE_TYPE,
    "text": "Welches Wort passt?",
    "options": [{"text": "Das", "correct": True}, {"text": "Der", "correct": False}],
}
GAP = {"type": FREE_TEXT_TYPE, "text": "Ich ___ zur Arbeit.", "answers": ["gehe"]}
FREE = {"type": FREE_TEXT_TYPE, "text": "Schreibe ueber deinen Tag."}


def test_a_finished_plan_has_no_incomplete_question():
    assert first_incomplete_question(_raw(CHOICE, GAP, FREE)) is None


def test_the_shipped_german_plan_passes_its_own_rule():
    """Der ausgelieferte Standard muss speicherbar sein, sonst ist die Regel falsch."""
    assert first_incomplete_question(json.dumps(DEFAULT_GERMAN_QUESTION_PLAN)) is None


def test_choice_without_question_text_is_incomplete():
    assert first_incomplete_question(_raw({**CHOICE, "text": ""})) == 1


def test_choice_without_options_is_incomplete():
    naked = {"type": CHOICE_TYPE, "text": "Welches Wort passt?"}
    assert first_incomplete_question(_raw(naked)) == 1


def test_free_text_needs_only_the_question_text():
    """Die Loesung ist freiwillig: ohne sie beurteilt die KI die Antwort, das ist
    kein fehlendes Feld sondern der Normalfall."""
    assert first_incomplete_question(_raw(FREE)) is None
    assert first_incomplete_question(_raw(GAP)) is None


def test_free_text_without_question_text_is_incomplete():
    assert first_incomplete_question(_raw({"type": FREE_TEXT_TYPE})) == 1


def test_the_first_incomplete_row_is_reported():
    """Die Nummer ist 1-basiert und zeigt auf die erste Luecke, nicht die letzte."""
    assert first_incomplete_question(
        _raw(CHOICE, {"type": FREE_TEXT_TYPE}, {"type": CHOICE_TYPE})
    ) == 2


# ─── Kein Erzeugen mehr waehrend des Tests ──────────────────────────────────

from src.services.aia_diagnosis_chat import (  # noqa: E402
    parse_question_plan,
    question_mode,
)


def test_no_stored_plan_gives_the_german_default():
    assert parse_question_plan("") == DEFAULT_GERMAN_QUESTION_PLAN


def test_a_stored_plan_with_an_unfinished_row_falls_back_to_the_default():
    """Altbestand aus der Zeit, als eine halbe Zeile erlaubt war.

    Speichern verhindert so etwas heute, in der Datenbank kann es noch stehen.
    Dann laeuft der Test auf dem Standard statt auf einer Frage ohne Text.
    """
    half = _raw(CHOICE, {"type": CHOICE_TYPE, "text": "Welches Wort passt?"})
    assert parse_question_plan(half) == DEFAULT_GERMAN_QUESTION_PLAN


def test_every_shipped_question_is_served_from_the_plan():
    """Kein Modus mehr, der das Modell um eine Frage bittet."""
    modes = {question_mode(step) for step in DEFAULT_GERMAN_QUESTION_PLAN}
    assert modes <= {"manual_options", "manual_typed", "manual_text"}


# ─── Der Speicherweg ────────────────────────────────────────────────────────

import pytest  # noqa: E402
from fastapi import HTTPException  # noqa: E402

from src.routes.admin import settings as admin_settings  # noqa: E402
from src.services.aia_diagnosis_chat import QUESTION_PLAN_SETTING  # noqa: E402

FIX = {"type": FREE_TEXT_TYPE, "text": "Der Satz hat einen Fehler: Gestern ich habe geschlafen."}


class _Body:
    """Minimaler Ersatz für UpdateSettingsRequest: alles None ausser einem Feld."""

    def __init__(self, **kwargs):
        object.__setattr__(self, "_set", kwargs)

    def __getattr__(self, name):
        return object.__getattribute__(self, "_set").get(name)

    def model_dump(self):
        # Der Speicher-Endpunkt laeuft die Felder ab, um jedes gegen ein Recht
        # zu pruefen. Was hier nicht drinsteht, gilt als nicht mitgeschickt.
        return dict(object.__getattribute__(self, "_set"))


@pytest.fixture
def store(monkeypatch):
    data = {}
    monkeypatch.setattr(
        admin_settings.db, "get_setting", lambda key, default="": data.get(key, default)
    )
    monkeypatch.setattr(
        admin_settings.db, "set_setting", lambda key, value: data.__setitem__(key, value)
    )
    return data


async def test_patch_stores_a_finished_plan(store):
    payload = _raw(CHOICE, GAP, FREE, FIX)
    await admin_settings.update_settings(
        _Body(language_diagnosis_question_plan_de=payload), _ADMIN, "de"
    )
    assert store[QUESTION_PLAN_SETTING] == payload


async def test_patch_rejects_an_unfinished_row_and_names_it(store):
    payload = _raw(CHOICE, {"type": CHOICE_TYPE, "text": "Welches Wort passt?"}, FREE, FIX)
    with pytest.raises(HTTPException) as exc:
        await admin_settings.update_settings(
            _Body(language_diagnosis_question_plan_de=payload), _ADMIN, "de"
        )
    assert exc.value.status_code == 400
    assert "2" in exc.value.detail
    assert QUESTION_PLAN_SETTING not in store
