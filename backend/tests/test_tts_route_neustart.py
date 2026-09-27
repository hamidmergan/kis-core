"""Die Stimm-Einstellungen liegen ab dem Einreihen bereit, nicht erst ab dem Start."""

import json

import pytest

from src.routes import tts as route


class _Request:
    headers = {}


class _Client:
    def is_available(self):
        return True


@pytest.fixture
def stub(monkeypatch):
    abgelegt = {}
    monkeypatch.setattr("src.dependencies.get_tts_client_for_provider", lambda pid: _Client())
    for name in ("enforce_open_jobs", "enforce_tool_burst", "enforce_quota"):
        monkeypatch.setattr(route, name, lambda *a, **k: None)
    monkeypatch.setattr(route.db, "create_job", lambda *a, **k: None)
    monkeypatch.setattr(route.db, "set_job_input_path", lambda *a, **k: None)
    monkeypatch.setattr(route.db, "set_job_celery_task_id", lambda *a, **k: None)
    monkeypatch.setattr(route, "save_queue_file_from_path", lambda uid, job, ext, pfad: "queue/in.txt")
    monkeypatch.setattr(route, "save_job_file",
                        lambda uid, job, name, daten: abgelegt.__setitem__(name, daten), raising=False)
    import src.tasks.tts_tasks as tt
    monkeypatch.setattr(tt, "run_tts", type("T", (), {"apply_async": staticmethod(
        lambda args=None, **k: type("R", (), {"id": "task-1"})())})())
    return abgelegt


async def test_ein_nie_gestarteter_auftrag_laesst_sich_fortsetzen(stub):
    """Lasttest 26.09.: vier Vorlese-Aufträge standen zu lange an und waren danach nicht mehr zu retten."""
    await route.text_to_speech(
        request=_Request(), file=None, text="Hallo Welt", voice_id="nova", speed=1.1,
        provider_id=21, voice_label="Nova", current_user={"user_id": 1}, locale="de")
    assert json.loads(stub["tts_params.json"]) == {
        "voice_id": "nova", "voice_label": "Nova", "speed": 1.1, "provider_id": 21}
