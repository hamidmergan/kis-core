"""Lernsätze, Datentabellen und Zeitpläne laufen über die Francis-Plätze und werden zurückgeholt.

Lasttest 26.09., Lauf 6: diese drei gingen an den Plätzen vorbei in die Schlange. Quellen standen
hinter 14 Lerntools, und fünf Lernsätze gingen bei einem Arbeiter-Neustart verloren und blieben
für immer auf "wird erzeugt".
"""

from pathlib import Path

import pytest

from src.features.ai_assistant.scheduling import reaper, service

ROUTEN = Path(__file__).resolve().parents[1] / "src" / "features" / "ai_assistant" / "routes"


@pytest.mark.parametrize("datei, task", [
    ("studio/flashcards.py", "run_generate_exercise_set"),
    ("language_training/exercises.py", "run_generate_exercise_set"),
    ("studio/data_table.py", "run_generate_data_table"),
    ("studio/schedule.py", "run_generate_schedule"),
])
def test_die_route_holt_sich_einen_platz(datei, task):
    text = (ROUTEN / datei).read_text()
    assert f"{task}.delay(" not in text
    assert "enqueue_task(" in text


@pytest.fixture
def abgeschlossen(monkeypatch):
    fertig = []
    monkeypatch.setattr(service, "on_complete", lambda uuid, **k: fertig.append(uuid))
    return fertig


def test_der_lernsatz_gibt_seinen_platz_zurueck(monkeypatch, abgeschlossen):
    import src.features.ai_assistant.tasks.language_training as mod

    class _DB:
        def get_aia_workspace_by_id(self, _id):
            return None

        def fail_exercise_set(self, _id):
            pass

    monkeypatch.setattr(mod, "db", _DB())
    mod.run_generate_exercise_set(1, 7, "quiz", "source", 10, _aia_job_uuid="a1")
    assert abgeschlossen == ["a1"]


def test_ein_wartender_lernsatz_behaelt_seinen_platz(monkeypatch, abgeschlossen):
    import src.features.ai_assistant.tasks.language_training as mod

    class _DB:
        def get_aia_workspace_by_id(self, _id):
            raise RuntimeError("Error code: 503 service unavailable")

    neu = []
    monkeypatch.setattr(mod, "db", _DB())
    monkeypatch.setattr(mod.run_generate_exercise_set, "apply_async",
                        lambda args=None, kwargs=None, countdown=None: neu.append(kwargs))
    mod.run_generate_exercise_set(1, 7, "quiz", "source", 10, _aia_job_uuid="a1")
    # The later run carries the seat along and gives it back itself.
    assert abgeschlossen == [] and neu[0]["_aia_job_uuid"] == "a1"


def test_die_datentabelle_gibt_ihren_platz_zurueck(monkeypatch, abgeschlossen):
    import src.features.ai_assistant.tasks._helpers as helpers
    import src.features.ai_assistant.tasks.studio.data_table as mod

    def kaputt(table_id, status, **k):
        if status == "running":
            raise RuntimeError("weg")

    monkeypatch.setattr(helpers, "learning_tools_language", lambda: ("de", "Deutsch"))
    monkeypatch.setattr(mod.db, "update_aia_data_table", kaputt)
    mod.run_generate_data_table.run(3, [1], ["u"], {}, _aia_job_uuid="a2")
    assert abgeschlossen == ["a2"]


def test_der_zeitplan_gibt_seinen_platz_zurueck(monkeypatch, abgeschlossen):
    import src.features.ai_assistant.tasks.studio.schedule as mod

    def kaputt(job_id, status, **k):
        if status == "running":
            raise RuntimeError("weg")

    monkeypatch.setattr(mod.db, "update_schedule_job", kaputt)
    mod.run_generate_schedule.run(4, 7, 1, ["u"], _aia_job_uuid="a3")
    assert abgeschlossen == ["a3"]


@pytest.mark.parametrize("task, getter, zeile, erwartet", [
    ("aia.generate_exercise_set", "get_exercise_set_with_items", {"status": "generating"}, None),
    ("aia.generate_exercise_set", "get_exercise_set_with_items", {"status": "ready"}, "done"),
    ("aia.generate_exercise_set", "get_exercise_set_with_items", {"status": "failed"}, "failed"),
    ("aia.generate_data_table", "get_aia_data_table", {"status": "running"}, None),
    ("aia.generate_data_table", "get_aia_data_table", {"status": "success"}, "done"),
    ("aia.generate_schedule", "get_schedule_job", {"status": "pending"}, None),
    ("aia.generate_schedule", "get_schedule_job", {"status": "failed"}, "failed"),
    ("aia.generate_schedule", "get_schedule_job", None, "failed"),
])
def test_ein_verlorener_lauf_wird_nach_stand_neu_eingereiht(monkeypatch, task, getter, zeile, erwartet):
    from src import database as db

    monkeypatch.setattr(db, getter, lambda *a, **k: zeile, raising=False)
    assert reaper.outcome_of(task, {"args": [5, 7, 1, ["u"]]}) == erwartet
