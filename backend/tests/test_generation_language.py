"""Die Werkzeuge erzeugen ihre Inhalte in der Unterrichtssprache des Kursraums.

Nicht in der Oberflaechensprache der Person. Fuer einen Deutschkurs waere das falsch: wer
die Oberflaeche auf Englisch stellt, bekaeme eine englische Passiv-Uebung, an der es
nichts zu ueben gibt.

Und nicht fest verdrahtet: eine Hochschule, die auf Franzoesisch unterrichtet, stellt es
am Kursraum ein und alle Werkzeuge folgen. Standard ist Deutsch.
"""

import pytest

from src.features.ai_assistant.tasks._helpers import (
    TOOL_OUTPUT_LANGUAGE,
    tool_output_language,
)


def test_german_is_the_default():
    assert TOOL_OUTPUT_LANGUAGE == "German"
    assert tool_output_language(None) == ("de", "German")


def test_the_workspace_decides(monkeypatch):
    monkeypatch.setattr("src.database.get_aia_workspace_by_id",
                        lambda _id: {"id": 7, "diagnosis_language": "fr"})
    assert tool_output_language(7) == ("fr", "French")


@pytest.mark.parametrize("code,name", [
    ("de", "German"), ("en", "English"), ("fr", "French"), ("es", "Spanish"),
    ("it", "Italian"), ("tr", "Turkish"), ("ar", "Arabic"), ("ru", "Russian"),
])
def test_every_offered_language_resolves(monkeypatch, code, name):
    """Alle acht aus der Auswahlliste muessen ankommen, nicht nur die beiden gaengigen."""
    monkeypatch.setattr("src.database.get_aia_workspace_by_id",
                        lambda _id: {"id": 7, "diagnosis_language": code})
    assert tool_output_language(7) == (code, name)


def test_a_workspace_without_a_setting_gets_the_default(monkeypatch):
    monkeypatch.setattr("src.database.get_aia_workspace_by_id", lambda _id: {"id": 7})
    assert tool_output_language(7) == ("de", "German")


def test_an_unknown_code_falls_back_instead_of_crashing(monkeypatch):
    # Ein Wert, den niemand mehr anbietet, darf keinen Auftrag scheitern lassen.
    monkeypatch.setattr("src.database.get_aia_workspace_by_id",
                        lambda _id: {"id": 7, "diagnosis_language": "kli"})
    assert tool_output_language(7) == ("de", "German")


def test_an_unreadable_workspace_falls_back(monkeypatch):
    def boom(_id):
        raise RuntimeError("database is having a day")

    monkeypatch.setattr("src.database.get_aia_workspace_by_id", boom)
    assert tool_output_language(7) == ("de", "German")


def test_a_missing_workspace_falls_back(monkeypatch):
    monkeypatch.setattr("src.database.get_aia_workspace_by_id", lambda _id: None)
    assert tool_output_language(7) == ("de", "German")


def test_no_tool_derives_its_output_language_from_the_locale():
    """Die Ableitung aus der Oberflaechensprache darf nirgends wieder auftauchen.

    Der frueher an sechs Stellen kopierte Einzeiler ist genau die Art Fund, die beim
    naechsten Werkzeug versehentlich mitkopiert wird.

    Geprueft wird der Aufgaben-Baum. Notiz-Titel bleiben bewusst draussen: eine Notiz
    schreibt der Nutzer selbst, ihr Titel fasst seinen eigenen Text zusammen und gehoert
    deshalb in seine Sprache.
    """
    import pathlib

    wurzel = (pathlib.Path(__file__).resolve().parent.parent
              / "src" / "features" / "ai_assistant" / "tasks")
    treffer = [
        p.relative_to(wurzel).as_posix()
        for p in wurzel.rglob("*.py")
        if '"English" if' in p.read_text(encoding="utf-8")
    ]
    assert treffer == [], f"Ableitung aus dem locale wieder aufgetaucht in: {treffer}"
