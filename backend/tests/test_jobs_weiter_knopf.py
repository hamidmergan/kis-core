"""Der Weiter-Knopf rettet jeden angehaltenen Auftrag, dessen Angaben noch da sind."""

import json

import pytest
from fastapi import HTTPException

from src.routes.jobs import _retry as route


class _Db:
    def __init__(self, job):
        self.job = job
        self.eingereiht = []
        self.zurueckgesetzt = []

    def get_job(self, job_uuid):
        return self.job

    def transition_job_to_queued(self, job_uuid, user_id, from_statuses):
        self.eingereiht.append(job_uuid)
        return True

    def reset_attempts(self, job_uuid):
        self.zurueckgesetzt.append(job_uuid)

    def claim_job_for_retry(self, job_uuid):
        self.job["status"] = "running"
        return True


@pytest.fixture
def umgebung(monkeypatch):
    dateien = {}
    abgelegt = {}
    gestartet = []

    def lesen(uid, job, name):
        if name not in dateien:
            raise FileNotFoundError(name)
        return dateien[name]

    monkeypatch.setattr(route, "get_job_file", lesen)
    monkeypatch.setattr(route, "save_job_file", lambda uid, job, name, daten: abgelegt.__setitem__(name, daten))
    import src.tasks.screencast_tasks as sc
    monkeypatch.setattr(sc, "dispatch_next_screencast_job_for_user", lambda uid: gestartet.append(("sc", uid)))
    from src.services import job_recovery
    monkeypatch.setattr(job_recovery, "dispatch_resume", lambda job: gestartet.append(("resume", job["tool"])))
    return dateien, abgelegt, gestartet


def _job(tool, status="paused"):
    return {"job_uuid": "j", "user_id": 1, "tool": tool, "status": status, "progress": "{}",
            "attempts": 4, "input_path": None, "original_filename": "x"}


def test_ein_beim_uebersetzen_angehaltener_screencast_laeuft_weiter(umgebung, monkeypatch):
    """Lasttest 26.09.: "Render-Parameter nicht mehr vorhanden", obwohl nie vertont wurde."""
    dateien, abgelegt, gestartet = umgebung
    dateien["queue_params.json"] = json.dumps({"dispatch_as": "translate"}).encode()
    db = _Db(_job("screencast_translate"))
    monkeypatch.setattr(route, "db", db)

    assert route.retry_job("j", current_user={"user_id": 1}, locale="de") == {"ok": True}
    assert db.eingereiht == ["j"]
    assert gestartet == [("sc", 1)]
    # Die Übersetzungsangaben bleiben, wie sie waren.
    assert "queue_params.json" not in abgelegt


def test_ein_screencast_ganz_ohne_angaben_bleibt_ehrlich_abgelehnt(umgebung, monkeypatch):
    db = _Db(_job("screencast_translate"))
    monkeypatch.setattr(route, "db", db)
    with pytest.raises(HTTPException) as fehler:
        route.retry_job("j", current_user={"user_id": 1}, locale="de")
    assert fehler.value.status_code == 400


def test_eine_angehaltene_zusammenfassung_laeuft_weiter(umgebung, monkeypatch):
    """Bisher gab es für sie keinen Knopf, sie war eine Sackgasse."""
    dateien, _, gestartet = umgebung
    dateien["summary_params.json"] = json.dumps({"template_slug": "kurzbriefing", "provider_id": None}).encode()
    db = _Db(_job("summary"))
    monkeypatch.setattr(route, "db", db)

    assert route.retry_job("j", current_user={"user_id": 1}, locale="de") == {"ok": True}
    assert gestartet == [("resume", "summary")]


def test_eine_zusammenfassung_ohne_angaben_wird_abgelehnt(umgebung, monkeypatch):
    db = _Db(_job("summary"))
    monkeypatch.setattr(route, "db", db)
    with pytest.raises(HTTPException) as fehler:
        route.retry_job("j", current_user={"user_id": 1}, locale="de")
    assert fehler.value.status_code == 400
