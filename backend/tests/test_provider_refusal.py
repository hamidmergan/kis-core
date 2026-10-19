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
    monkeypatch.setattr(provider_check, "refused_ids", lambda feature, ids=None: {21} if feature == "chat" else set())

    result = await svc.list_reachable_choices("chat")
    assert [p["id"] for p in result["providers"]] == [20, 22]
    assert result["default_id"] == 20


@pytest.fixture(autouse=True)
def _frische_pruefungen(monkeypatch):
    monkeypatch.setattr(provider_check, "_running", {})
    monkeypatch.setattr(provider_check, "_last_start", {})


def _ziele(*ids):
    return [("chat", {"id": i, "name": f"P{i}"}, "m") for i in ids] + [("tts", {"id": 21, "name": "P21"}, None)]


def test_alte_ergebnisse_werden_sofort_und_parallel_neu_geprueft(monkeypatch):
    from datetime import datetime, timedelta

    jetzt = datetime.now().isoformat()
    alt = (datetime.now() - timedelta(hours=1)).isoformat()
    stand = {(20, "chat"): {"status": "ok", "checked_at": jetzt},
             (21, "chat"): {"status": "ok", "checked_at": alt},
             (21, "tts"): {"status": "error", "checked_at": alt}}
    geprueft = []

    def check(feature, provider, model):
        geprueft.append((provider["id"], feature))
        stand[(provider["id"], feature)] = {"status": "error", "checked_at": datetime.now().isoformat()}

    monkeypatch.setattr(provider_check, "targets", lambda: _ziele(20, 21, 22))
    monkeypatch.setattr(provider_check.provider_checks, "list_checks", lambda: dict(stand))
    monkeypatch.setattr(provider_check, "_check_one", check)

    assert provider_check.refused_ids("chat", {20, 21, 22}) == {21, 22}
    assert sorted(geprueft) == [(21, "chat"), (22, "chat")]


def test_nur_die_anbieter_im_dropdown_werden_geprueft(monkeypatch):
    geprueft = []
    monkeypatch.setattr(provider_check, "targets", lambda: _ziele(20, 21))
    monkeypatch.setattr(provider_check.provider_checks, "list_checks", lambda: {})
    monkeypatch.setattr(provider_check, "_check_one", lambda f, p, m: geprueft.append(p["id"]))

    assert provider_check.refused_ids("chat", {21, 99}) == set()
    assert geprueft == [21]


def test_eine_langsame_pruefung_behaelt_ihr_letztes_ergebnis(monkeypatch):
    import threading
    from datetime import datetime, timedelta

    alt = (datetime.now() - timedelta(hours=1)).isoformat()
    frei = threading.Event()
    monkeypatch.setattr(provider_check, "PROVIDER_CHECK_DROPDOWN_WAIT_SECONDS", 0.1)
    monkeypatch.setattr(provider_check, "targets", lambda: _ziele(20))
    monkeypatch.setattr(provider_check.provider_checks, "list_checks",
                        lambda: {(20, "chat"): {"status": "error", "checked_at": alt}})
    monkeypatch.setattr(provider_check, "_check_one", lambda f, p, m: frei.wait(5))

    try:
        assert provider_check.refused_ids("chat") == {20}
    finally:
        frei.set()


def test_ein_nicht_gespeichertes_ergebnis_hebt_die_grenze_nicht_auf(monkeypatch):
    geprueft = []

    def check(feature, provider, model):
        geprueft.append(provider["id"])
        raise RuntimeError("database gone")

    monkeypatch.setattr(provider_check, "targets", lambda: _ziele(20))
    monkeypatch.setattr(provider_check.provider_checks, "list_checks", lambda: {})
    monkeypatch.setattr(provider_check, "_check_one", check)

    for _ in range(3):
        assert provider_check.refused_ids("chat") == set()
    assert geprueft == [20]
    assert provider_check._running == {}


def test_funktionen_ohne_pruefung_blenden_nichts_aus():
    assert provider_check.refused_ids("stt") == set()
