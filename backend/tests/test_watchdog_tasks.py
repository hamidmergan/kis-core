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
    # The shared pool of the assistant has its own test, here it must not touch the real one.
    monkeypatch.setattr(watchdog_tasks, "_reap_aia_slots", lambda: None)
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



def _wartend(task_id="t-1", status="pending"):
    return {"job_uuid": "j", "tool": "tts", "status": status, "creator_locale": "de",
            "celery_task_id": task_id, "progress_updated_at": None}


def _broker(monkeypatch, waiting=(), taken=()):
    from src.services.broker_state import Snapshot
    monkeypatch.setattr(watchdog_tasks.broker_state, "snapshot",
                        lambda: Snapshot(waiting=set(waiting), taken=set(taken)))


def test_ein_auftrag_der_nur_in_der_schlange_wartet_gilt_nicht_als_haengend(umgebung, monkeypatch):
    """Lasttest 26.09.: 20 Leute, alle Plätze voll, nach 10 Minuten Warten war der Auftrag tot."""
    db, anlaeufe, abgeschossen, _ = umgebung
    db.haengend = [_wartend("t-1")]
    _broker(monkeypatch, waiting={"t-1"})

    watchdog_tasks.check_stuck_jobs()

    assert anlaeufe == []
    assert abgeschossen == []


def test_ein_gerade_abgeholter_wartender_auftrag_bleibt_in_ruhe(umgebung, monkeypatch):
    db, anlaeufe, _, _ = umgebung
    db.haengend = [_wartend("t-1")]
    _broker(monkeypatch, taken={"t-1"})

    watchdog_tasks.check_stuck_jobs()

    assert anlaeufe == []


def test_die_naechste_etappe_in_der_schlange_gilt_nicht_als_haengend(umgebung, monkeypatch):
    """Eine Etappe reiht sich neu ein und die Zeile bleibt auf running, auch während sie ansteht."""
    db, anlaeufe, _, _ = umgebung
    db.haengend = [_wartend("t-2", status="running")]
    _broker(monkeypatch, waiting={"t-2"})

    watchdog_tasks.check_stuck_jobs()

    assert anlaeufe == []


def test_ein_wartender_auftrag_ohne_nachricht_beim_broker_ist_verloren(umgebung, monkeypatch):
    db, anlaeufe, _, _ = umgebung
    db.haengend = [_wartend("t-weg")]
    _broker(monkeypatch, waiting={"t-1"})

    watchdog_tasks.check_stuck_jobs()

    assert [a[0] for a in anlaeufe] == ["j"]


def test_ist_der_broker_nicht_lesbar_bleiben_wartende_auftraege_in_ruhe(umgebung, monkeypatch):
    db, anlaeufe, _, _ = umgebung
    db.haengend = [_wartend("t-1")]
    monkeypatch.setattr(watchdog_tasks.broker_state, "snapshot", lambda: None)

    watchdog_tasks.check_stuck_jobs()

    assert anlaeufe == []


def test_ein_laufender_auftrag_ohne_lebenszeichen_bleibt_haengend(umgebung, monkeypatch):
    """Ein abgeholter Auftrag liegt immer unquittiert beim Broker, das entlastet ihn nicht."""
    db, anlaeufe, _, _ = umgebung
    db.haengend = [_wartend("t-1", status="running")]
    _broker(monkeypatch, taken={"t-1"})

    watchdog_tasks.check_stuck_jobs()

    assert [a[0] for a in anlaeufe] == ["j"]


def test_ein_leerer_broker_ist_eine_antwort_und_kein_unbekannt(umgebung, monkeypatch):
    db, anlaeufe, _, _ = umgebung
    db.haengend = [_wartend("t-weg")]
    _broker(monkeypatch)

    watchdog_tasks.check_stuck_jobs()

    assert [a[0] for a in anlaeufe] == ["j"]


def test_der_aufseher_holt_verwaiste_plaetze_zurueck_und_fuellt_nach(monkeypatch):
    """Ohne diesen Takt startet der Topf nur neu, wenn gerade ein Auftrag endet."""
    from src.features.ai_assistant.scheduling import reaper, service
    ablauf = []
    monkeypatch.setattr(watchdog_tasks.broker_state, "snapshot", lambda: "stand")
    monkeypatch.setattr(reaper, "reap", lambda store, stand, outcome: ablauf.append(("reap", stand)) or 1)

    class _Dienst:
        def dispatch(self):
            ablauf.append("dispatch")
            return []

    monkeypatch.setattr(service, "get_dispatch_service", lambda: _Dienst())
    watchdog_tasks._reap_aia_slots()
    assert ablauf == [("reap", "stand"), "dispatch"]
