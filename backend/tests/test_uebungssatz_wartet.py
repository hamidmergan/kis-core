"""Ein Übungssatz wartet, wenn nur das Modell zu langsam oder überlastet war.

Lasttest 26.09., Lauf 5: zwei Sätze liefen in drei Modell-Zeitüberschreitungen und dann in
die Zeitgrenze der Aufgabe. Sie landeten auf failed, obwohl nur der Anbieter zu voll war.
"""

from datetime import datetime, timedelta

import pytest
from celery.exceptions import SoftTimeLimitExceeded

from src.features.ai_assistant.tasks.language_training import run_generate_exercise_set


@pytest.fixture
def stack(monkeypatch):
    """Lets the context step throw what the test hands in and records the outcome."""
    import src.features.ai_assistant.tasks.language_training as mod

    seen = {"failed": False, "requeued": None, "fehler": None,
            "created_at": datetime.utcnow()}

    class _DB:
        def get_aia_workspace_by_id(self, _id):
            return {"id": 7}

        def get_exercise_set_with_items(self, _id):
            return {"user_id": 1, "created_at": seen["created_at"]}

        def fail_exercise_set(self, _id):
            seen["failed"] = True

    def _boom(*a, **k):
        raise seen["fehler"]

    def _apply_async(args=None, kwargs=None, countdown=None, **_):
        seen["requeued"] = {"args": args, "kwargs": kwargs, "countdown": countdown}

    monkeypatch.setattr(mod, "db", _DB())
    monkeypatch.setattr(mod, "_get_llm_client", lambda: (object(), "m", "p"))
    monkeypatch.setattr(mod, "build_adaptive_tool_suffix", lambda *a, **k: "")
    monkeypatch.setattr(mod, "build_title_avoidance_block", lambda *a, **k: "")
    monkeypatch.setattr(mod, "build_source_context", _boom)
    monkeypatch.setattr(mod.run_generate_exercise_set, "apply_async", _apply_async)
    return seen


def _run(anlauf=0):
    run_generate_exercise_set(1, 7, "quiz", "source", 10, source_uuids=["u-1"],
                              locale="de", anlauf=anlauf)


def test_ein_ueberlasteter_anbieter_reiht_den_satz_neu_ein(stack):
    stack["fehler"] = RuntimeError("Error code: 503 - service unavailable")

    _run()

    assert stack["failed"] is False
    neu = stack["requeued"]
    assert neu["args"] == [1, 7, "quiz", "source", 10]
    assert neu["kwargs"]["source_uuids"] == ["u-1"]
    assert 60 <= neu["countdown"] <= 180


def test_die_zeitgrenze_reiht_neu_ein_und_zaehlt_mit(stack):
    stack["fehler"] = SoftTimeLimitExceeded()

    _run(anlauf=1)

    assert stack["failed"] is False
    assert stack["requeued"]["kwargs"]["anlauf"] == 2


def test_nach_drei_zeitgrenzen_ist_schluss(stack):
    # A set that is simply too big must not circle for hours.
    stack["fehler"] = SoftTimeLimitExceeded()

    _run(anlauf=3)

    assert stack["failed"] is True
    assert stack["requeued"] is None


def test_nach_zwoelf_stunden_warten_ist_schluss(stack):
    stack["fehler"] = RuntimeError("Request timed out.")
    stack["created_at"] = datetime.utcnow() - timedelta(hours=13)

    _run()

    assert stack["failed"] is True
    assert stack["requeued"] is None


def test_ein_echter_fehler_scheitert_sofort(stack):
    stack["fehler"] = KeyError("front")

    _run()

    assert stack["failed"] is True
    assert stack["requeued"] is None
