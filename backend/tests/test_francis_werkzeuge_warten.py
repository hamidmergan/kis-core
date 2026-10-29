"""Mindmap, data table and schedule wait for an overloaded AI instead of aborting.

Load test 26.09.: a mindmap with only 2581 characters aborted after 4 minutes because the AI
was busy with the large documents of other services.
"""

import time

import pytest
from celery.exceptions import SoftTimeLimitExceeded

from src.features.ai_assistant.scheduling import service


def _mindmap():
    import src.features.ai_assistant.tasks.studio.mindmap as mod
    return mod, mod.run_generate_mindmap, "update_aia_mindmap", [1, [2], ["u"]]


def _tabelle():
    import src.features.ai_assistant.tasks.studio.data_table as mod
    return mod, mod.run_generate_data_table, "update_aia_data_table", [1, [2], ["u"], {}]


def _zeitplan():
    import src.features.ai_assistant.tasks.studio.schedule as mod
    return mod, mod.run_generate_schedule, "update_schedule_job", [1, 7, 3, ["u"]]


@pytest.fixture(params=[_mindmap, _tabelle, _zeitplan], ids=["mindmap", "tabelle", "zeitplan"])
def werkzeug(request, monkeypatch):
    import src.features.ai_assistant.tasks._helpers as helpers

    mod, task, schreiber, args = request.param()
    stand = {"status": [], "neu": [], "frei": [], "fehler": None}

    def schreiben(_id, status, **k):
        stand["status"].append(status)
        if status == "running":
            raise stand["fehler"]

    monkeypatch.setattr(helpers, "learning_tools_language", lambda: ("de", "Deutsch"))
    monkeypatch.setattr(mod.db, schreiber, schreiben)
    monkeypatch.setattr(task, "apply_async",
                        lambda args=None, kwargs=None, countdown=None: stand["neu"].append((args, kwargs, countdown)))
    monkeypatch.setattr(service, "on_complete", lambda uuid, **k: stand["frei"].append(uuid))
    return task, args, stand


def test_eine_ueberlastete_ki_reiht_neu_ein_und_behaelt_den_platz(werkzeug):
    task, args, stand = werkzeug
    stand["fehler"] = RuntimeError("Request timed out.")

    task.run(*args, _aia_job_uuid="a1")

    assert "failed" not in stand["status"] and stand["frei"] == []
    neu_args, kwargs, warte = stand["neu"][0]
    assert neu_args == args and kwargs["_aia_job_uuid"] == "a1" and kwargs["anlauf"] == 1
    assert 60 <= warte <= 180


def test_ein_echter_fehler_scheitert_und_gibt_den_platz_frei(werkzeug):
    task, args, stand = werkzeug
    stand["fehler"] = KeyError("nodes")

    task.run(*args, _aia_job_uuid="a1")

    assert stand["status"][-1] == "failed" and stand["frei"] == ["a1"] and stand["neu"] == []


def test_nach_drei_zeitgrenzen_ist_schluss(werkzeug):
    task, args, stand = werkzeug
    stand["fehler"] = SoftTimeLimitExceeded()

    task.run(*args, _aia_job_uuid="a1", anlauf=3)

    assert stand["status"][-1] == "failed" and stand["neu"] == []


def _versteckte_zeitgrenze():
    """The deadline the way the OpenAI SDK hands it on: wrapped in a connection error."""
    import httpx
    import openai
    try:
        try:
            raise SoftTimeLimitExceeded()
        except SoftTimeLimitExceeded as innen:
            raise openai.APIConnectionError(request=httpx.Request("POST", "http://x")) from innen
    except openai.APIConnectionError as aussen:
        return aussen


def test_eine_versteckte_zeitgrenze_zaehlt_als_zeitgrenze_nicht_als_wartende_ki(werkzeug):
    """On 07.10. a mindmap retried for 12 hours this way instead of ending after 3 runs."""
    task, args, stand = werkzeug
    stand["fehler"] = _versteckte_zeitgrenze()

    task.run(*args, _aia_job_uuid="a1", anlauf=3)

    assert stand["status"][-1] == "failed" and stand["neu"] == []


def test_eine_versteckte_zeitgrenze_darf_vorher_neu_einreihen(werkzeug):
    task, args, stand = werkzeug
    stand["fehler"] = _versteckte_zeitgrenze()

    task.run(*args, _aia_job_uuid="a1", anlauf=0)

    assert len(stand["neu"]) == 1


def test_nach_einer_viertelstunde_warten_ist_schluss(werkzeug):
    # A person waits in front of the tool, twelve hours like a service was far too long.
    task, args, stand = werkzeug
    stand["fehler"] = RuntimeError("503 service unavailable")

    task.run(*args, _aia_job_uuid="a1", anlauf=5, seit=time.time() - 16 * 60)

    assert stand["status"][-1] == "failed" and stand["neu"] == []


def test_vor_einer_viertelstunde_wartet_das_tool_noch(werkzeug):
    task, args, stand = werkzeug
    stand["fehler"] = RuntimeError("503 service unavailable")

    task.run(*args, _aia_job_uuid="a1", anlauf=5, seit=time.time() - 10 * 60)

    assert len(stand["neu"]) == 1


class _NeuerLauf:
    name = "aia.generate_mindmap"

    def apply_async(self, args=None, kwargs=None, countdown=None):
        return type("R", (), {"id": "neu-1"})()


def test_der_platz_kennt_nach_dem_warten_die_neue_auftragsnummer(monkeypatch):
    """Run 14: 20 mindmaps ran twice, the supervisor lost the old id and restarted them."""
    from src.features.ai_assistant.repository import jobs as repo
    from src.features.ai_assistant.tasks import _warten

    gemerkt = {}
    monkeypatch.setattr(repo.DbJobStore, "set_celery_task_id", lambda self, platz, tid: gemerkt.update({platz: tid}))

    assert _warten.wieder_einreihen(_NeuerLauf(), SoftTimeLimitExceeded(), anlauf=0, seit=None,
                                    args=[1], kwargs={"_aia_job_uuid": "platz-1"})
    assert gemerkt == {"platz-1": "neu-1"}


def test_der_uebungssatz_gibt_seinem_platz_die_neue_auftragsnummer(monkeypatch):
    from src.features.ai_assistant.repository import jobs as repo
    from src.features.ai_assistant.tasks import language_training as lt

    gemerkt = {}
    monkeypatch.setattr(repo.DbJobStore, "set_celery_task_id", lambda self, platz, tid: gemerkt.update({platz: tid}))
    monkeypatch.setattr(lt.run_generate_exercise_set, "apply_async", _NeuerLauf().apply_async)

    assert lt._wieder_einreihen(SoftTimeLimitExceeded(), None, 0, [1, 2, "quiz", "source", 10],
                                {"_aia_job_uuid": "platz-2"})
    assert gemerkt == {"platz-2": "neu-1"}
