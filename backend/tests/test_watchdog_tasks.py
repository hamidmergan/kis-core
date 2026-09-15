"""Der Aufseher: faellige Auftraege starten, haengende einsammeln, geparkte verfallen lassen."""

import pytest

from src.tasks import watchdog_tasks


class _Db:
    def __init__(self):
        self.haengend = []
        self.abgelaufen = []
        self.verfallen = []

    def get_stuck_running_jobs(self, threshold_minutes):
        return self.haengend

    def get_stale_awaiting_user_jobs(self, threshold_hours):
        return self.abgelaufen

    def expire_parked_job(self, job_uuid, message):
        self.verfallen.append((job_uuid, message))


@pytest.fixture
def umgebung(monkeypatch):
    db = _Db()
    anlaeufe = []
    abgeschossen = []
    faellig = {"n": 0}

    monkeypatch.setattr(watchdog_tasks, "db", db)
    monkeypatch.setattr(watchdog_tasks.job_recovery, "attempt_failed",
                        lambda job_uuid, message, **k: anlaeufe.append((job_uuid, message, k)) or "waiting_retry")
    monkeypatch.setattr(watchdog_tasks.job_recovery, "resume_due_jobs",
                        lambda: faellig.__setitem__("n", faellig["n"] + 1) or 0)
    monkeypatch.setattr(watchdog_tasks.celery_app.control, "revoke",
                        lambda tid, **k: abgeschossen.append(tid))
    return db, anlaeufe, abgeschossen, faellig


def test_faellige_auftraege_werden_bei_jedem_takt_gestartet(umgebung):
    _, _, _, faellig = umgebung
    watchdog_tasks.check_stuck_jobs()
    assert faellig["n"] == 1


def test_ein_haengender_auftrag_zaehlt_als_ein_anlauf_mit_schranke(umgebung):
    db, anlaeufe, _, _ = umgebung
    db.haengend = [{"job_uuid": "j", "tool": "podcast", "creator_locale": "de",
                    "celery_task_id": "t-1", "progress_updated_at": None}]

    watchdog_tasks.check_stuck_jobs()

    assert len(anlaeufe) == 1
    assert anlaeufe[0][0] == "j"
    assert anlaeufe[0][2]["stale_before"] is not None


def test_der_haengende_lauf_wird_wirklich_beendet(umgebung):
    db, _, abgeschossen, _ = umgebung
    db.haengend = [{"job_uuid": "j", "tool": "podcast", "creator_locale": "de",
                    "celery_task_id": "t-1", "progress_updated_at": None}]

    watchdog_tasks.check_stuck_jobs()

    assert abgeschossen == ["t-1"]


def test_ein_inzwischen_gemeldeter_auftrag_wird_nicht_abgeschossen(umgebung, monkeypatch):
    db, _, abgeschossen, _ = umgebung
    db.haengend = [{"job_uuid": "j", "tool": "podcast", "creator_locale": "de",
                    "celery_task_id": "t-1", "progress_updated_at": None}]
    monkeypatch.setattr(watchdog_tasks.job_recovery, "attempt_failed",
                        lambda job_uuid, message, **k: None)

    watchdog_tasks.check_stuck_jobs()

    assert abgeschossen == []


def test_ein_geparkter_auftrag_verfaellt_nach_der_frist(umgebung):
    db, _, _, _ = umgebung
    db.abgelaufen = [{"job_uuid": "alt", "tool": "podcast", "creator_locale": "de"}]

    watchdog_tasks.check_stuck_jobs()

    assert db.verfallen[0][0] == "alt"


def test_ein_fehler_beim_wiederanlauf_stoppt_die_anderen_pflichten_nicht(umgebung, monkeypatch):
    db, _, _, _ = umgebung
    monkeypatch.setattr(watchdog_tasks.job_recovery, "resume_due_jobs",
                        lambda: (_ for _ in ()).throw(RuntimeError("DB weg")))
    db.abgelaufen = [{"job_uuid": "alt", "tool": "podcast", "creator_locale": "de"}]

    watchdog_tasks.check_stuck_jobs()

    assert db.verfallen[0][0] == "alt"
