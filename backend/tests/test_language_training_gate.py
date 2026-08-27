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
# Ein Satz je Lager: der eine gehoert dem Sprachtrainer, der andere den Lernwerkzeugen.
LERNKARTEN_SATZ = {"id": 1, "workspace_id": 7, "user_id": LERNENDER, "tool": "flashcards"}
KARTEIKARTEN_SATZ = {"id": 2, "workspace_id": 7, "user_id": LERNENDER, "tool": "karteikarten"}


@pytest.fixture
def trainer_aus(monkeypatch):
    """Workspace da, Lernender eingeschrieben, Sprachtrainer abgeschaltet."""
    for modul in (_helpers, diagnosis, exercises):
        monkeypatch.setattr(modul.db, "get_aia_workspace", lambda uuid: WORKSPACE)
        monkeypatch.setattr(modul.db, "is_student_enrolled", lambda ws_id, uid: True)
        monkeypatch.setattr(modul.db, "is_workspace_tutor", lambda ws_id, uid: False)
        monkeypatch.setattr(modul.db, "is_language_training_active", lambda ws_id: False)
    monkeypatch.setattr(exercises.db, "get_exercise_set_meta", lambda sid: LERNKARTEN_SATZ)


@pytest.fixture
def ohne_bremsen(monkeypatch):
    """Tempo- und Kontingentpruefung stillgelegt, hier geht es nur um die Sperre."""
    monkeypatch.setattr(exercises, "enforce_aia_burst", lambda *a, **k: None)
    monkeypatch.setattr(exercises, "enforce_quota", lambda *a, **k: None)


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


# Karteikarten und Quiz laufen ueber dieselbe Route, gehoeren aber zu den
# Lernwerkzeugen. Der abgeschaltete Sprachtrainer darf sie nicht mitnehmen.


def _fehlende_quelle(tool: str) -> int:
    from src.features.ai_assistant import schemas

    with pytest.raises(HTTPException) as fehler:
        asyncio.run(
            exercises.create_exercise_set(
                "w-1",
                schemas.CreateSetBody(tool=tool, mode="source"),
                current_user=_nutzer(),
                locale="de",
            )
        )
    return fehler.value.status_code


def test_karteikarten_brauchen_den_trainer_nicht(trainer_aus, ohne_bremsen):
    """400 wegen der fehlenden Quelle heisst: die Sperre hat durchgelassen."""
    assert _fehlende_quelle("karteikarten") == 400


def test_quiz_braucht_den_trainer_nicht(trainer_aus, ohne_bremsen):
    assert _fehlende_quelle("quiz") == 400


def test_karteikarten_duerfen_wiederholt_werden(trainer_aus, ohne_bremsen, monkeypatch):
    """409 statt 403: der Satz ist nur nicht fehlgeschlagen."""
    monkeypatch.setattr(exercises.db, "get_exercise_set_meta", lambda sid: KARTEIKARTEN_SATZ)
    monkeypatch.setattr(exercises.db, "reset_exercise_set_for_retry", lambda sid, uid: None)

    with pytest.raises(HTTPException) as fehler:
        asyncio.run(
            exercises.retry_exercise_set(
                "w-1",
                2,
                current_user=_nutzer(),
                locale="de",
            )
        )
    assert fehler.value.status_code == 409
