"""The watchdog reclaims orphaned seats in the shared pool; on 26.09. four seats lost to a Postgres crash blocked every upload for three hours."""

from src.features.ai_assistant.scheduling import reaper
from src.services.broker_state import Snapshot


class _Store:
    def __init__(self, zeilen):
        self.zeilen = zeilen
        self.beendet = []
        self.zurueck = []

    def running_rows(self):
        return self.zeilen

    def mark_finished(self, job_uuid, ok, error):
        self.beendet.append((job_uuid, ok))

    def requeue(self, job_uuid):
        self.zurueck.append(job_uuid)


def _zeile(job="a", task_id="t-1", vor=600, task="aia.index_source"):
    return {"job_uuid": job, "task_name": task, "payload": {"args": ["src-1", "de"]},
            "celery_task_id": task_id, "started_at": 10_000 - vor}


def test_ein_verwaister_unfertiger_auftrag_kommt_zurueck_in_die_schlange():
    store = _Store([_zeile()])
    reaper.reap(store, Snapshot(), lambda task, payload: None, now=10_000)
    assert store.zurueck == ["a"]
    assert store.beendet == []


def test_ein_verwaister_aber_fertiger_auftrag_gibt_nur_den_platz_frei():
    """The work was done, only the report failed, so do not compute again."""
    store = _Store([_zeile()])
    reaper.reap(store, Snapshot(), lambda task, payload: "done", now=10_000)
    assert store.beendet == [("a", True)]
    assert store.zurueck == []


def test_ein_verwaister_gescheiterter_auftrag_bleibt_gescheitert():
    store = _Store([_zeile()])
    reaper.reap(store, Snapshot(), lambda task, payload: "failed", now=10_000)
    assert store.beendet == [("a", False)]


def test_ein_auftrag_den_der_broker_noch_haelt_bleibt_unberuehrt():
    store = _Store([_zeile(task_id="t-1")])
    reaper.reap(store, Snapshot(taken={"t-1"}), lambda task, payload: None, now=10_000)
    assert store.zurueck == [] and store.beendet == []


def test_ein_gerade_gestarteter_auftrag_bekommt_eine_schonfrist():
    """Between taking a seat and writing the id there is a brief moment without an id."""
    store = _Store([_zeile(task_id=None, vor=5)])
    reaper.reap(store, Snapshot(), lambda task, payload: None, now=10_000)
    assert store.zurueck == [] and store.beendet == []


def test_ohne_broker_antwort_wird_nichts_angefasst():
    store = _Store([_zeile()])
    assert reaper.reap(store, None, lambda task, payload: None, now=10_000) == 0
    assert store.zurueck == [] and store.beendet == []
