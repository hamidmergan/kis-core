"""A build resumes with its finished parts, a half-written outline is worth nothing."""

import json

from src.services import job_recovery


def _job(step, status="waiting_retry"):
    return {"job_uuid": "d" * 32, "user_id": 7, "tool": "praesentation", "status": status,
            "progress": json.dumps({"step": step}), "attempts": 2, "creator_locale": "en"}


def test_gliederung_wird_nicht_wieder_aufgenommen():
    assert job_recovery.resume_entry(_job("outline")) is None


def test_bau_wird_wieder_aufgenommen():
    assert job_recovery.resume_entry(_job("bilder")) == "praesentation"


def test_dispatch_reiht_den_bau_mit_dem_anlauf_token_ein(monkeypatch):
    eingereiht = []

    class _Task:
        def apply_async(self, args):
            eingereiht.append(list(args))
            return type("T", (), {"id": "x"})()

    monkeypatch.setattr("src.tasks.praesentation_tasks.run_praesentation_build", _Task())
    monkeypatch.setattr(job_recovery.db, "set_job_celery_task_id", lambda *a: None)
    monkeypatch.setattr("src.tasks.podcast_tasks._shared.clear_cancel", lambda j: None)
    job_recovery.dispatch_resume(_job("texte"))
    assert eingereiht == [["d" * 32, 7, "en", 1, 2, None, False]]


def test_wiederanlauf_behaelt_das_fertigstellen(monkeypatch):
    """A job parked mid-finalize must re-queue with the same finalize intent, or the download never opens."""
    eingereiht = []

    class _Task:
        def apply_async(self, args):
            eingereiht.append(list(args))
            return type("T", (), {"id": "x"})()

    monkeypatch.setattr("src.tasks.praesentation_tasks.run_praesentation_build", _Task())
    monkeypatch.setattr(job_recovery.db, "set_job_celery_task_id", lambda *a: None)
    monkeypatch.setattr("src.tasks.podcast_tasks._shared.clear_cancel", lambda j: None)
    job = {"job_uuid": "d" * 32, "user_id": 7, "tool": "praesentation", "status": "waiting_retry",
           "progress": json.dumps({"step": "bau", "final": True}), "attempts": 1, "creator_locale": "en"}
    job_recovery.dispatch_resume(job)
    assert eingereiht == [["d" * 32, 7, "en", 1, 1, None, True]]




