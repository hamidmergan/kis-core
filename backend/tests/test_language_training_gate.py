"""Schaltet die Verwaltung den Sprachtrainer ab, ist er im Kurs sofort zu.

Das Sprachniveau haengt am Nutzer, nicht am Workspace, und es bleibt beim
Abschalten gespeichert. Genau darum reicht es nicht, die Kacheln auszublenden:
ein offen gebliebenes Fenster wuerde sonst weiter Uebungen erzeugen und den
Einstufungstest zu Ende laufen lassen. Chat und Werkzeuge pruefen den Schalter
schon laenger, hier sind die Sprachtrainer-Routen selbst dran.

Das Niveau selbst wird nicht geloescht. Wer den Trainer spaeter wieder
einschaltet, findet die Einstufung vor, statt sie noch einmal machen zu muessen.
"""

import asyncio

import pytest
from fastapi import HTTPException

from src.features.ai_assistant.routes import _helpers
from src.features.ai_assistant.routes.language_training import diagnosis, exercises

LERNENDER = 3
WORKSPACE = {"id": 7, "uuid": "w-1", "user_id": 1, "diagnosis_language": "de"}


@pytest.fixture
def trainer_aus(monkeypatch):
    """Workspace da, Lernender eingeschrieben, Sprachtrainer abgeschaltet."""
    for modul in (_helpers, diagnosis, exercises):
        monkeypatch.setattr(modul.db, "get_aia_workspace", lambda uuid: WORKSPACE)
        monkeypatch.setattr(modul.db, "is_student_enrolled", lambda ws_id, uid: True)
        monkeypatch.setattr(modul.db, "is_workspace_tutor", lambda ws_id, uid: False)
        monkeypatch.setattr(modul.db, "is_language_training_active", lambda ws_id: False)


def _nutzer() -> dict:
    return {"user_id": LERNENDER, "role": "user", "email": ""}


def test_einstufungstest_laeuft_nicht_weiter(trainer_aus):
    """Ein offener Test darf nach dem Abschalten nicht zu Ende gehen."""
    with pytest.raises(HTTPException) as fehler:
        asyncio.run(
            diagnosis.turn(
                diagnosis.TurnBody(workspace_uuid="w-1", history=[]),
                current_user=_nutzer(),
                llm=None,
                locale="de",
            )
        )
    assert fehler.value.status_code == 403


def test_uebungen_werden_nicht_mehr_erzeugt(trainer_aus):
    from src.features.ai_assistant import schemas

    with pytest.raises(HTTPException) as fehler:
        asyncio.run(
            exercises.create_exercise_set(
                "w-1",
                schemas.CreateSetBody(tool="flashcards"),
                current_user=_nutzer(),
                locale="de",
            )
        )
    assert fehler.value.status_code == 403


def test_fehlgeschlagene_uebung_wird_nicht_wiederholt(trainer_aus):
    with pytest.raises(HTTPException) as fehler:
        asyncio.run(
            exercises.retry_exercise_set(
                "w-1",
                1,
                current_user=_nutzer(),
                locale="de",
            )
        )
    assert fehler.value.status_code == 403
