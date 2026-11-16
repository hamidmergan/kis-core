"""Deleting a job stops its worker and clears its traces, for the owner and for an admin alike."""

from src.routes.admin import jobs as admin_jobs
from src.routes.jobs import _cancel, _download, _shared


def _job(tool: str = "screencast_render") -> dict:
    return {"job_uuid": "a" * 32, "user_id": 7, "tool": tool, "celery_task_id": "task-1"}


class _Redis:
    def __init__(self, calls: list):
        self.calls = calls

    def setex(self, key, ttl, value):
        self.calls.append(("setex", key, ttl))

    def delete(self, key):
        self.calls.append(("delete", key))

    def publish(self, channel, message):
        self.calls.append(("publish", channel))

    def close(self):
        pass


def _wire(monkeypatch) -> list:
    calls: list = []
    monkeypatch.setattr("redis.from_url", lambda *a, **k: _Redis(calls))
    monkeypatch.setattr(_cancel.celery_app.control, "revoke", lambda task_id, **k: calls.append(("revoke", task_id)))
    monkeypatch.setattr(_cancel, "delete_job_folder", lambda uid, job: calls.append(("folder", uid, job)))
    monkeypatch.setattr(_cancel.db, "delete_job", lambda job: calls.append(("row", job)))
    monkeypatch.setattr("src.tasks.screencast_tasks.dispatch_next_screencast_job_for_user",
                        lambda uid: calls.append(("next", uid)))
    return calls


def test_remove_job_stops_the_worker_before_it_deletes(monkeypatch):
    calls = _wire(monkeypatch)
    _cancel.remove_job(_job())
    assert calls == [
        ("revoke", "task-1"),
        ("setex", "job:cancel:" + "a" * 32, 600),
        ("folder", 7, "a" * 32),
        ("row", "a" * 32),
        ("publish", "jobs:7"),
        ("next", 7),
    ]


def test_only_a_screencast_lets_the_next_one_run(monkeypatch):
    calls = _wire(monkeypatch)
    _cancel.remove_job(_job(tool="tts"))
    assert ("next", 7) not in calls


def test_admin_delete_sets_the_cancel_flag_too(monkeypatch):
    calls = _wire(monkeypatch)
    monkeypatch.setattr(admin_jobs.db, "get_job", lambda job: _job())
    assert admin_jobs.admin_cancel_job("a" * 32, _admin={}, locale="de") == {"ok": True}
    assert ("setex", "job:cancel:" + "a" * 32, 600) in calls
    assert ("next", 7) in calls


def test_retry_clears_the_flag_a_cancel_set(monkeypatch):
    calls = _wire(monkeypatch)
    _shared.set_cancel_flag("b" * 32)
    _shared.clear_cancel_flag("b" * 32)
    assert calls == [("setex", "job:cancel:" + "b" * 32, 600), ("delete", "job:cancel:" + "b" * 32)]


def test_bundle_and_pptx_names_survive_any_script(monkeypatch):
    monkeypatch.setattr(_download.db, "get_job", lambda job: {**_job(), "original_filename": "x.pptx"})
    monkeypatch.setattr(_download, "load_result_meta", lambda uid, job: {"result_stem": "講義 Vorlesung"})
    monkeypatch.setattr(_download, "get_job_file", lambda uid, job, name: b"PK")
    monkeypatch.setattr(_download, "baue_info", lambda *a, **k: "")
    for antwort in (
        _download.download_job_pptx("a" * 32, current_user={"user_id": 7}, locale="de"),
        _download.download_job_bundle("a" * 32, current_user={"user_id": 7}, locale="de"),
    ):
        kopf = antwort.headers["content-disposition"]
        kopf.encode("latin-1")
        assert "filename*=UTF-8''%E8%AC%9B%E7%BE%A9%20Vorlesung" in kopf
