"""Die eine Fehlerbahn: ein paar Anlaeufe von selbst, dann angehalten und warten."""

import json

import pytest

from src.limits import MAX_AUTO_RESUMES, RETRY_BACKOFF_SECONDS
from src.services import job_recovery


class _Db:
    """Merkt sich jeden Schreibzugriff, damit der Test die Bahn nachlesen kann."""

    def __init__(self, job=None):
        self.job = job or {}
        self.versuche = []
        self.gescheitert = []
        self.task_ids = []
        self.claim = None
        self.faellig = []
        self.in_flight = []

    def get_job(self, job_uuid):
        return self.job or None

    def record_failed_attempt(self, job_uuid, message, *, max_resumes, backoff,
                              paused_message=None, stale_before=None):
        n = (self.job.get("attempts") or 0) + 1
        self.job["attempts"] = n
        status = "waiting_retry" if n <= max_resumes else "paused"
        self.versuche.append({
            "n": n, "status": status, "message": message,
            "paused_message": paused_message, "stale_before": stale_before,
            "wartezeit": backoff[min(n, len(backoff)) - 1] if status == "waiting_retry" else None,
        })
        return status

    def update_job_status(self, job_uuid, status, error_message=None, progress=None):
        self.gescheitert.append((status, error_message))

    def job_claim(self, job_uuid):
        return self.claim

    def claim_due_retries(self, limit=20):
        faellig, self.faellig = self.faellig, []
        return faellig

    def jobs_in_flight(self):
        return self.in_flight

    def set_job_celery_task_id(self, job_uuid, task_id):
        self.task_ids.append(task_id)


class _FakeTask:
    """Ein Celery-Task, der nur merkt, womit er abgeschickt wurde."""

    def __init__(self):
        self.args = None

    def apply_async(self, args=None, **kwargs):
        self.args = args
        return type("R", (), {"id": "task-1"})()


@pytest.fixture
def db(monkeypatch):
    fake = _Db({"job_uuid": "j", "tool": "podcast", "user_id": 7, "creator_locale": "de",
                "attempts": 0, "progress": json.dumps({"step": "tts"})})
    monkeypatch.setattr(job_recovery, "db", fake)
    return fake


class TestLeiter:
    def test_die_ersten_drei_anlaeufe_warten_eine_drei_und_zehn_minuten(self, db):
        gesehen = []
        for _ in range(MAX_AUTO_RESUMES):
            gesehen.append(job_recovery.attempt_failed("j", "Anbieter weg"))
        assert gesehen == ["waiting_retry"] * MAX_AUTO_RESUMES
        assert [v["wartezeit"] for v in db.versuche] == list(RETRY_BACKOFF_SECONDS)

    def test_der_vierte_fehlschlag_haelt_an(self, db):
        for _ in range(MAX_AUTO_RESUMES):
            job_recovery.attempt_failed("j", "Anbieter weg")
        assert job_recovery.attempt_failed("j", "Anbieter immer noch weg") == "paused"

    def test_die_angehalten_meldung_nennt_die_zahl_der_anlaeufe(self, db):
        for _ in range(MAX_AUTO_RESUMES + 1):
            job_recovery.attempt_failed("j", "Anbieter weg")
        text = db.versuche[-1]["paused_message"]
        assert str(MAX_AUTO_RESUMES) in text and "Anbieter weg" in text

    def test_der_waechter_reicht_seine_schranke_durch(self, db):
        job_recovery.attempt_failed("j", "haengt", stale_before="cutoff")
        assert db.versuche[0]["stale_before"] == "cutoff"


class TestWasNichtWiederAnlaeuft:
    def test_ein_fremdes_werkzeug_geht_direkt_auf_fehlgeschlagen(self, db):
        db.job["tool"] = "translate"
        assert job_recovery.attempt_failed("j", "kaputt") == "failed"
        assert db.gescheitert == [("failed", "kaputt")]
        assert db.versuche == []

    def test_ein_podcast_im_skript_schritt_geht_direkt_auf_fehlgeschlagen(self, db):
        db.job["progress"] = json.dumps({"step": "script"})
        assert job_recovery.attempt_failed("j", "kaputt") == "failed"

    def test_ein_podcast_in_der_vertonung_laeuft_wieder_an(self, db):
        assert job_recovery.attempt_failed("j", "kaputt") == "waiting_retry"


class TestStillMine:
    def test_gleicher_stand_gehoert_der_etappe(self, db):
        db.claim = ("running", 2)
        assert job_recovery.still_mine("j", 2)

    def test_ein_anderer_zaehler_gehoert_einem_neueren_lauf(self, db):
        db.claim = ("running", 3)
        assert not job_recovery.still_mine("j", 2)

    def test_ein_geparkter_auftrag_gehoert_niemandem_mehr(self, db):
        db.claim = ("paused", 2)
        assert not job_recovery.still_mine("j", 2)

    def test_ein_geloeschter_auftrag_gehoert_niemandem_mehr(self, db):
        db.claim = None
        assert not job_recovery.still_mine("j", 2)


class TestWiederanlauf:
    def test_der_podcast_bekommt_etappe_eins_und_den_zaehler(self, db, monkeypatch):
        task = _FakeTask()
        geloescht = []
        import src.tasks.podcast_tasks as pt
        import src.tasks.podcast_tasks._shared as shared
        monkeypatch.setattr(pt, "run_podcast_render", task)
        monkeypatch.setattr(shared, "clear_cancel", geloescht.append)

        job_recovery.dispatch_resume({"job_uuid": "j", "user_id": 7, "tool": "podcast",
                                      "creator_locale": "de", "attempts": 2,
                                      "progress": json.dumps({"step": "tts"})})

        assert task.args == ["j", 7, "de", 1, 2]
        assert geloescht == ["j"]
        assert db.task_ids == ["task-1"]

    def test_der_screencast_geht_durch_seine_warteschlange(self, db, monkeypatch):
        gerufen = []
        import src.tasks.screencast_tasks._queue as queue
        monkeypatch.setattr(queue, "dispatch_next_screencast_job_for_user", gerufen.append)

        job_recovery.dispatch_resume({"job_uuid": "j", "user_id": 7, "tool": "screencast_render",
                                      "creator_locale": "de", "attempts": 1, "progress": "{}"})

        assert gerufen == [7]

    def test_ein_nicht_absendbarer_auftrag_bleibt_nicht_liegen(self, db, monkeypatch):
        db.faellig = [{"job_uuid": "j", "user_id": 7, "tool": "podcast",
                       "creator_locale": "de", "attempts": 1, "progress": "{}"}]
        monkeypatch.setattr(job_recovery, "dispatch_resume",
                            lambda job: (_ for _ in ()).throw(RuntimeError("Broker weg")))

        assert job_recovery.resume_due_jobs() == 1
        assert db.versuche[-1]["message"] == "Broker weg"


class TestNeustart:
    def test_ein_laufender_auftrag_wird_sofort_faellig_und_behaelt_die_anlaeufe(self, db):
        db.in_flight = [dict(db.job, attempts=1)]
        assert job_recovery.recover_after_restart() == 1
        assert db.versuche[-1]["status"] == "waiting_retry"
        assert db.versuche[-1]["wartezeit"] == 0

    def test_ein_nicht_wiederaufnehmbarer_auftrag_geht_auf_fehlgeschlagen(self, db):
        db.in_flight = [dict(db.job, tool="translate")]
        job_recovery.recover_after_restart()
        assert db.gescheitert[-1][0] == "failed"
