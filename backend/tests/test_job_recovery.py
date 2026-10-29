"""The single failure path: a few automatic retries, then paused and waiting."""

import json

import pytest

from src.limits import (
    MAX_AUTO_RESUMES, PROVIDER_BUSY_MAX_HOURS, PROVIDER_BUSY_WAIT_SECONDS, RETRY_BACKOFF_SECONDS,
)
from src.services import job_recovery


class _Db:
    """Records every write so the test can replay the path."""

    def __init__(self, job=None):
        self.job = job or {}
        self.versuche = []
        self.gescheitert = []
        self.task_ids = []
        self.claim = None
        self.faellig = []
        self.in_flight = []
        self.gewartet = []

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

    def touch_job_heartbeat(self, job_uuid):
        self.lebenszeichen = getattr(self, "lebenszeichen", 0) + 1

    def claim_due_retries(self, limit=20):
        faellig, self.faellig = self.faellig, []
        return faellig

    def jobs_in_flight(self):
        return self.in_flight

    def set_job_celery_task_id(self, job_uuid, task_id):
        self.task_ids.append(task_id)

    def record_busy_wait(self, job_uuid, message, *, wait_seconds):
        self.gewartet.append({"message": message, "wartezeit": wait_seconds})
        return "waiting_retry"


class _FakeTask:
    """A Celery task that only records what it was sent with."""

    def __init__(self):
        self.args = None

    def apply_async(self, args=None, **kwargs):
        self.args = args
        self.priority = kwargs.get("priority")
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


class TestResumeTuer:
    def test_eine_zusammenfassung_geht_ueber_ihre_eigene_tuer(self):
        assert job_recovery.resume_entry({"tool": "summary"}) == "summary"


class TestUeberlastImErstenSchritt:
    """Script and outline read large documents, an overloaded model must not end them."""

    def test_ein_podcast_skript_wartet_bei_ueberlast(self, db):
        db.job["progress"] = json.dumps({"step": "script"})
        assert job_recovery.attempt_failed("j", "voll", busy=True) == "waiting_retry"
        assert db.gescheitert == []

    def test_eine_gliederung_wartet_bei_ueberlast(self, db):
        db.job.update(tool="praesentation", progress=json.dumps({"step": "outline"}))
        assert job_recovery.attempt_failed("j", "voll", busy=True) == "waiting_retry"

    def test_eine_kaputte_gliederung_scheitert_wie_bisher(self, db):
        db.job.update(tool="praesentation", progress=json.dumps({"step": "outline"}))
        assert job_recovery.attempt_failed("j", "kaputt") == "failed"
        assert db.versuche == []

    def test_das_skript_laeuft_ueber_seine_eigene_tuer_wieder_an(self, db, monkeypatch):
        task = _FakeTask()
        import src.tasks.podcast_tasks as pt
        import src.tasks.podcast_tasks._shared as shared
        monkeypatch.setattr(pt, "run_podcast_script", task)
        monkeypatch.setattr(shared, "clear_cancel", lambda j: None)

        job_recovery.dispatch_resume({"job_uuid": "j", "user_id": 7, "tool": "podcast", "creator_locale": "de",
                                      "attempts": 0, "progress": json.dumps({"step": "script"})})

        assert task.args == ["j", 7, "de", 1, 0]

    def test_die_gliederung_laeuft_ueber_ihre_eigene_tuer_wieder_an(self, db, monkeypatch):
        task = _FakeTask()
        import src.tasks.praesentation_tasks as prt
        import src.tasks.podcast_tasks._shared as shared
        monkeypatch.setattr(prt, "run_praesentation_outline", task)
        monkeypatch.setattr(shared, "clear_cancel", lambda j: None)

        job_recovery.dispatch_resume({"job_uuid": "j", "user_id": 7, "tool": "praesentation",
                                      "creator_locale": "de", "attempts": 0,
                                      "progress": json.dumps({"step": "outline"})})

        assert task.args == ["j", 7, "de", 1, 0]

    def test_ein_wiederanlauf_reiht_sich_hinter_neuer_arbeit_ein(self, db, monkeypatch):
        """Run 14: seven scripts kept timing out and instantly retook one of the three seats, starving 20 presentations, 17 translations and 5 transcripts for over an hour."""
        task = _FakeTask()
        import src.tasks.podcast_tasks as pt
        import src.tasks.podcast_tasks._shared as shared
        monkeypatch.setattr(pt, "run_podcast_script", task)
        monkeypatch.setattr(shared, "clear_cancel", lambda j: None)

        job_recovery.dispatch_resume({"job_uuid": "j", "user_id": 7, "tool": "podcast", "creator_locale": "de",
                                      "attempts": 0, "progress": json.dumps({"step": "script"})})

        assert task.priority == 9


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

    def test_eine_uebernommene_etappe_meldet_sich_sofort(self, db):
        """After a long wait the last heartbeat is old, the watchdog must not catch them."""
        db.claim = ("running", 2)
        job_recovery.still_mine("j", 2)
        assert db.lebenszeichen == 1

    def test_eine_fremde_etappe_meldet_nichts(self, db):
        db.claim = ("running", 3)
        job_recovery.still_mine("j", 2)
        assert getattr(db, "lebenszeichen", 0) == 0

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

    def test_die_zusammenfassung_bekommt_ihre_angaben_und_den_zaehler(self, db, monkeypatch):
        task = _FakeTask()
        import src.storage as storage
        import src.tasks.summary_tasks as st
        monkeypatch.setattr(st, "run_summary", task)
        monkeypatch.setattr(storage, "get_job_file", lambda uid, job, name: json.dumps({
            "sources": [{"filename": "a.txt", "input_path": "p1"}],
            "template_slug": "kurzbriefing", "provider_id": 3,
        }).encode())

        job_recovery.dispatch_resume({"job_uuid": "j", "user_id": 7, "tool": "summary",
                                      "creator_locale": "de", "attempts": 2, "progress": "{}"})

        assert task.args == ["j", "kurzbriefing", 3, 2]
        assert db.task_ids == ["task-1"]


class TestSummaryParams:
    def test_liest_die_angaben_aus_der_ablage(self, monkeypatch):
        import src.storage as storage
        monkeypatch.setattr(storage, "get_job_file", lambda uid, job, name: json.dumps({
            "sources": [{"filename": "a.txt", "input_path": "p1"}],
            "template_slug": "kurzbriefing", "provider_id": None,
        }).encode())

        angaben = job_recovery._summary_params({"user_id": 7, "job_uuid": "j"})

        assert angaben == {"sources": [{"filename": "a.txt", "input_path": "p1"}],
                           "template_slug": "kurzbriefing", "provider_id": None}

    def test_ohne_die_datei_bricht_es_verstaendlich_ab(self, monkeypatch):
        import src.storage as storage

        def _fehlt(uid, job, name):
            raise FileNotFoundError(name)

        monkeypatch.setattr(storage, "get_job_file", _fehlt)
        with pytest.raises(RuntimeError):
            job_recovery._summary_params({"user_id": 7, "job_uuid": "j"})


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


class TestAnbieterVoll:
    """Load test 26.09.: myLab was merely full, yet all renderings paused after 15 minutes."""

    def test_ein_voller_anbieter_verbraucht_keinen_anlauf(self, db):
        for _ in range(MAX_AUTO_RESUMES + 5):
            assert job_recovery.attempt_failed("j", "voll", busy=True) == "waiting_retry"
        assert db.versuche == []
        assert len(db.gewartet) == MAX_AUTO_RESUMES + 5

    def test_die_wartezeit_streut_damit_nicht_alle_gleichzeitig_zurueckkommen(self, db):
        for _ in range(20):
            job_recovery.attempt_failed("j", "voll", busy=True)
        zeiten = {round(w["wartezeit"]) for w in db.gewartet}
        assert len(zeiten) > 1
        assert all(PROVIDER_BUSY_WAIT_SECONDS[0] <= w["wartezeit"] <= PROVIDER_BUSY_WAIT_SECONDS[1]
                   for w in db.gewartet)

    def test_nach_der_hoechstwartezeit_zaehlt_es_doch_als_anlauf(self, db):
        from datetime import datetime, timedelta, timezone
        db.job["created_at"] = datetime.now(timezone.utc) - timedelta(hours=PROVIDER_BUSY_MAX_HOURS + 1)
        job_recovery.attempt_failed("j", "voll", busy=True)
        assert db.gewartet == []
        assert len(db.versuche) == 1

    def test_ein_echter_fehler_zaehlt_weiter_als_anlauf(self, db):
        job_recovery.attempt_failed("j", "kaputt")
        assert len(db.versuche) == 1
        assert db.gewartet == []
