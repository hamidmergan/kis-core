"""19.10.2026: myLab answered every Pages call with 401, the jobs kept trying and the dropdown kept showing it."""
import pytest

from src.services import feature_provider_choices as svc
from src.services import job_recovery, provider_check
from src.services.upstream_errors import is_provider_refusal, is_upstream_busy


@pytest.mark.parametrize("meldung", [
    "Error code: 401 - {'message': 'Failed to process request'}",
    "Error code: 403 - Forbidden",
    "Error code: 404 - model not found",
    "Client error '400 Bad Request' for url 'http://x/v1/chat/completions'",
])
def test_eine_absage_wird_erkannt_und_ist_kein_stau(meldung):
    assert is_provider_refusal(RuntimeError(meldung))
    assert not is_upstream_busy(RuntimeError(meldung))


@pytest.mark.parametrize("meldung", [
    "Error code: 429 - Too Many Requests",
    "Error code: 502 - Bad Gateway",
    "list index out of range",
    "Folie 401 fehlt",
])
def test_stau_und_eigene_fehler_sind_keine_absage(meldung):
    assert not is_provider_refusal(RuntimeError(meldung))


def test_die_absage_wird_auch_in_der_kette_gefunden():
    try:
        try:
            raise RuntimeError("Error code: 401 - Unauthorized")
        except RuntimeError as inner:
            raise RuntimeError("Folie 3 ging nicht") from inner
    except RuntimeError as outer:
        assert is_provider_refusal(outer)


class _Db:
    def __init__(self, job):
        self.job = job
        self.status = []
        self.versuche = 0

    def get_job(self, job_uuid):
        return self.job

    def update_job_status(self, job_uuid, status, error_message=None, progress=None):
        self.status.append(status)

    def record_failed_attempt(self, *a, **kw):
        self.versuche += 1
        return "waiting_retry"


def test_ein_abgelehnter_auftrag_endet_sofort_ohne_neuen_anlauf(monkeypatch):
    fake = _Db({"job_uuid": "j", "tool": "pages", "status": "running", "attempts": 0})
    monkeypatch.setattr(job_recovery, "db", fake)
    assert job_recovery.attempt_failed("j", "abgelehnt", refused=True) == "failed"
    assert fake.status == ["failed"] and fake.versuche == 0


def test_ein_schon_beendeter_auftrag_bleibt_wie_er_ist(monkeypatch):
    fake = _Db({"job_uuid": "j", "tool": "pages", "status": "failed", "attempts": 0})
    monkeypatch.setattr(job_recovery, "db", fake)
    assert job_recovery.attempt_failed("j", "abgelehnt", refused=True) is None
    assert fake.status == []


class _Ok:
    def probe(self):
        from src.services.protocols.base import ProbeResult

        return ProbeResult(capabilities=[], status="ok", error=None)


async def test_das_dropdown_zeigt_keinen_anbieter_dessen_letzter_echter_aufruf_scheiterte(monkeypatch):
    providers = [{"id": i, "name": f"P{i}", "protocol": "openai_compat", "base_url": f"http://p{i}",
                  "api_key": None, "enabled": True, "capabilities": ["chat"]} for i in (20, 21, 22)]
    monkeypatch.setattr(svc.db, "list_providers_with_capability", lambda cap: providers)
    monkeypatch.setattr(svc.db, "get_route",
                        lambda f: {"provider_id": 21, "model_name": "m", "provider_models": {"20": "m", "22": "m"}})
    monkeypatch.setattr(svc, "make_adapter", lambda **kw: _Ok())
    monkeypatch.setattr(provider_check, "refused_ids", lambda feature: {21} if feature == "chat" else set())

    result = await svc.list_reachable_choices("chat")
    assert [p["id"] for p in result["providers"]] == [20, 22]
    assert result["default_id"] == 20


def test_ein_veralteter_stand_stoesst_eine_neue_pruefung_an(monkeypatch):
    gestartet = []
    monkeypatch.setattr(provider_check, "_stale", lambda: True)
    monkeypatch.setattr(provider_check.threading, "Thread",
                        lambda target, kwargs, daemon: type("T", (), {"start": lambda self: gestartet.append(kwargs)})())
    monkeypatch.setattr(provider_check.provider_checks, "list_checks", lambda: {
        (21, "chat"): {"status": "error"}, (20, "chat"): {"status": "ok"}, (21, "tts"): {"status": "error"},
        (22, "chat"): {"status": "busy"},
    })
    assert provider_check.refused_ids("chat") == {21}
    assert gestartet == [{"force": False}]


def test_funktionen_ohne_pruefung_blenden_nichts_aus():
    assert provider_check.refused_ids("stt") == set()
