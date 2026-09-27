"""Eine Übersetzung wartet bei vollem Anbieter und reiht sich neu ein, statt zu scheitern.

Lauf 15, 27.09.: Mit der Obergrenze von 10 LLM-Plätzen bei myLab warteten Übersetzungen 120 s
auf einen Platz und scheiterten dann endgültig, weil nur die Transkription neu einreihte.
"""
import contextlib

import pytest

from src.services.provider_slots import ProviderFull
from src.tasks import general_tasks as gt


class _Req:
    def __init__(self, retries):
        self.retries = retries


class _Retrying(Exception):
    """Stand-in for celery's Retry, so we can assert self.retry fired and stop."""


class _FakeSelf:
    def __init__(self, retries=0):
        self.request = _Req(retries)
        self.retry_calls: list[tuple] = []

    def retry(self, exc=None, countdown=None, max_retries=None):
        self.retry_calls.append((countdown, max_retries))
        raise _Retrying()


@pytest.fixture
def env(monkeypatch):
    monkeypatch.setattr(gt.db, "update_job_status", lambda *a, **k: None)
    monkeypatch.setattr(gt, "_resolve_user_id", lambda j: 1)
    monkeypatch.setattr(gt, "get_file", lambda p: b"Hallo Welt")

    @contextlib.contextmanager
    def fake_hb(job_uuid):
        yield

    monkeypatch.setattr(gt, "job_heartbeat", fake_hb)
    failed: dict = {}
    monkeypatch.setattr(gt, "_handle_task_exception",
                        lambda j, e, task_label=None: failed.update({"err": str(e), "label": task_label}))

    class _Service:
        def __init__(self, **k):
            pass

        def translate_filename(self, name, *a):
            return name

        def translate_text(self, *a):
            raise stand["fehler"]

    stand = {"fehler": ValueError("Error processing DOCX file: " + str(ProviderFull("21:llm", 120)))}
    monkeypatch.setattr(gt, "TranslationService", _Service)
    monkeypatch.setattr(gt, "get_translate_client_for_provider", lambda *a, **k: (object(), None))
    return stand, failed


def _run(self_obj):
    return gt.run_translate.run.__func__(self_obj, "job1", "ip", "a.txt", "", "", "EN-US", None)


def test_ein_voller_anbieter_reiht_neu_ein(env):
    stand, failed = env
    s = _FakeSelf(retries=0)
    with pytest.raises(_Retrying):
        _run(s)
    assert s.retry_calls == [(30, 5)]
    assert failed == {}


def test_nach_fuenf_anlaeufen_ist_schluss(env):
    stand, failed = env
    s = _FakeSelf(retries=5)
    with pytest.raises(ValueError):
        _run(s)
    assert s.retry_calls == []
    assert failed.get("label") == "Translate"


def test_ein_echter_fehler_reiht_nicht_neu_ein(env):
    stand, failed = env
    stand["fehler"] = ValueError("Unsupported format: .xyz")
    s = _FakeSelf(retries=0)
    with pytest.raises(ValueError):
        _run(s)
    assert s.retry_calls == []
    assert failed.get("label") == "Translate"
