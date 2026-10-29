"""Text-to-audio fixes provider and voice on the first run, afterwards they never change.

User decision 27.09.2026: if the chosen provider is down at start the whole job runs with the admin fallback; stages, restarts and retries keep this choice.
"""

import json

import pytest
from fastapi import HTTPException

from src.routes import tts as route
from src.services import job_recovery, open_jobs, tts_job_provider
from src.services.tts_job_provider import VoicePick
from src.tasks import tts_tasks
from tests.test_tts_task_etappen import JOB, UID, _lauf, umgebung  # noqa: F401 - fixture

FESTGELEGT = {"voice_id": "onyx", "voice_label": "Onyx", "speed": 1.0, "provider_id": 21,
              "requested_provider_id": 2, "fallback": True, "pinned": True}


class _Sprecher:
    """Remembers which provider spoke with which voice."""

    def __init__(self):
        self.gesprochen = []

    def fuer(self, pid, user_id=None):
        sprecher = self

        class _C:
            def synthesize_chunk(self, text, voice_id="", speed=1.0, language="de"):
                sprecher.gesprochen.append((pid, voice_id))
                return b"ton"

        return _C()


@pytest.fixture
def welt(umgebung, monkeypatch):  # noqa: F811 - fixture from the stage tests
    db, ablage, _client, task, _a = umgebung
    sprecher = _Sprecher()
    gefragt = []

    def rueckfall(pid, stimmen):
        gefragt.append((pid, list(stimmen)))
        return VoicePick(21, ("onyx",), True)

    monkeypatch.setattr("src.dependencies.get_tts_client_for_provider", sprecher.fuer)
    monkeypatch.setattr(tts_tasks, "pick", rueckfall)
    monkeypatch.setattr(tts_tasks, "voice_name", lambda pid, vid: {"onyx": "Onyx"}.get(vid, vid))
    return db, ablage, sprecher, task, gefragt


def test_beim_ersten_lauf_ohne_gewaehlten_anbieter_spricht_alles_der_rueckfall(welt):
    db, ablage, sprecher, _task, gefragt = welt

    _lauf()

    assert gefragt == [(2, ["v1"])]
    assert sprecher.gesprochen == [(21, "onyx")] * 3
    assert json.loads(ablage.dateien["tts_params.json"]) == FESTGELEGT
    assert all(p["tts_params"] == FESTGELEGT for s, p in db.status if p)


def test_ist_der_gewaehlte_da_bleibt_name_und_stimme_wie_gewaehlt(welt, monkeypatch):
    _db, ablage, sprecher, _task, _g = welt
    monkeypatch.setattr(tts_tasks, "pick", lambda pid, stimmen: VoicePick(pid, tuple(stimmen), False))

    _lauf()

    assert sprecher.gesprochen == [(2, "v1")] * 3
    assert json.loads(ablage.dateien["tts_params.json"]) == {
        "voice_id": "v1", "voice_label": "Stimme", "speed": 1.0, "provider_id": 2,
        "requested_provider_id": 2, "fallback": False, "pinned": True}


def test_eine_festgelegte_stimme_gilt_auch_gegen_veraltete_argumente(welt):
    """A first stage redelivered after a crash still carries the chosen voice."""
    _db, ablage, sprecher, _task, gefragt = welt
    ablage.dateien["tts_params.json"] = json.dumps(FESTGELEGT).encode()

    _lauf()

    assert gefragt == []
    assert sprecher.gesprochen == [(21, "onyx")] * 3
    assert json.loads(ablage.dateien["tts_params.json"]) == FESTGELEGT


def test_die_naechste_etappe_bekommt_die_festgelegte_stimme(welt, monkeypatch):
    _db, _ablage, sprecher, task, _g = welt
    uhr = iter([False, True, True, True])
    monkeypatch.setattr(tts_tasks, "StageClock",
                        lambda *a, **k: type("C", (), {"over": staticmethod(lambda: next(uhr))})())

    _lauf()

    assert sprecher.gesprochen == [(21, "onyx")]
    assert task.aufrufe == [[JOB, "ein.txt", "ein.txt", "onyx", 1.0, 21, "Onyx", 0]]


def test_stuecke_eines_alten_laufs_halten_die_stimme_der_argumente(welt):
    """Never two voices in one file: what is already spoken decides the rest."""
    _db, ablage, sprecher, _task, gefragt = welt
    ablage.dateien["chunk_000.mp3"] = b"alt"

    _lauf()

    assert gefragt == []
    assert sprecher.gesprochen == [(2, "v1")] * 2
    gespeichert = json.loads(ablage.dateien["tts_params.json"])
    assert (gespeichert["provider_id"], gespeichert["voice_id"], gespeichert["pinned"]) == (2, "v1", True)
    assert gespeichert["fallback"] is False


def test_der_wiederanlauf_nach_pause_spricht_mit_der_festgelegten_stimme(welt, monkeypatch):
    _db, ablage, _sprecher, _task, _g = welt
    _lauf()
    monkeypatch.setattr("src.storage.get_job_file", ablage.get)
    gesendet = []
    monkeypatch.setattr(tts_tasks, "run_tts", type("T", (), {"apply_async": staticmethod(
        lambda args=None, **k: gesendet.append(args) or type("R", (), {"id": "t"})())})())
    monkeypatch.setattr(job_recovery.db, "set_job_celery_task_id", lambda *a: None)

    job_recovery.dispatch_resume({"job_uuid": JOB, "user_id": UID, "tool": "tts", "progress": "{}",
                                  "input_path": "ein.txt", "original_filename": "ein.txt", "attempts": 2})

    assert gesendet == [[JOB, "ein.txt", "ein.txt", "onyx", 1.0, 21, "Onyx", 2]]


def test_der_neuversuch_von_hand_spricht_mit_der_festgelegten_stimme(welt, monkeypatch):
    _db, ablage, _sprecher, _task, _g = welt
    _lauf()
    from src.routes.jobs import _retry
    gesendet = []
    monkeypatch.setattr(tts_tasks, "run_tts", type("T", (), {"apply_async": staticmethod(
        lambda args=None, **k: gesendet.append(args) or type("R", (), {"id": "t"})())})())
    monkeypatch.setattr(_retry, "get_job_file", ablage.get)
    monkeypatch.setattr(_retry, "enforce_open_jobs", lambda *a, **k: None)
    monkeypatch.setattr(_retry.db, "get_job", lambda j: {
        "job_uuid": JOB, "user_id": UID, "tool": "tts", "status": "paused", "progress": "{}",
        "input_path": "ein.txt", "original_filename": "ein.txt"})
    monkeypatch.setattr(_retry.db, "claim_job_for_retry", lambda j: True)
    monkeypatch.setattr(_retry.db, "set_job_celery_task_id", lambda *a: None)
    monkeypatch.setattr("redis.from_url", lambda *a, **k: type("R", (), {"delete": lambda s, k: 0})())

    _retry.retry_job(JOB, current_user={"user_id": UID}, locale="de")

    assert gesendet == [[JOB, "ein.txt", "ein.txt", "onyx", 1.0, 21, "Onyx", 0]]


class _Aussetzer(Exception):
    """A brief storage error, the file is there anyway."""

    response = {"Error": {"Code": "SlowDown"}}


def _gewaehlter_ist_da(monkeypatch, gefragt):
    def wahl(pid, stimmen):
        gefragt.append((pid, list(stimmen)))
        return VoicePick(pid, tuple(stimmen), False)

    monkeypatch.setattr(tts_tasks, "pick", wahl)


def test_ein_kurzer_ablagefehler_ueberschreibt_die_festgelegte_stimme_nie(welt, monkeypatch):
    """A redelivered first stage rather fails than fixing a second voice from old arguments."""
    _db, ablage, sprecher, _task, gefragt = welt
    ablage.dateien["tts_params.json"] = json.dumps(FESTGELEGT).encode()
    _gewaehlter_ist_da(monkeypatch, gefragt)

    def lesen(uid, job, name):
        if name == "tts_params.json":
            raise _Aussetzer("Ablage kurz weg")
        return ablage.get(uid, job, name)

    monkeypatch.setattr(tts_tasks, "get_job_file", lesen)

    with pytest.raises(_Aussetzer):
        _lauf()

    assert gefragt == []
    assert sprecher.gesprochen == []
    assert json.loads(ablage.dateien["tts_params.json"]) == FESTGELEGT


def test_fehlt_die_datei_gilt_die_festlegung_aus_dem_fortschritt(welt, monkeypatch):
    db, ablage, sprecher, _task, gefragt = welt
    _gewaehlter_ist_da(monkeypatch, gefragt)
    monkeypatch.setattr(db, "get_job", lambda j: {
        "user_id": UID, "creator_locale": "de",
        "progress": json.dumps({"step": "synthesize", "chunk": 2, "total": 3, "tts_params": FESTGELEGT})})

    _lauf()

    assert gefragt == []
    assert sprecher.gesprochen == [(21, "onyx")] * 3
    assert json.loads(ablage.dateien["tts_params.json"]) == FESTGELEGT


# ─── Accepting the job ─────────────────────────────────────────────────────


class _Request:
    headers = {}


@pytest.fixture
def annahme(monkeypatch):
    # The own probe of the client says down, only the view of the job's choice counts.
    stand = {"client": type("C", (), {"is_available": lambda self: False})(), "da": False, "rueckfall": True}
    abgelegt, eingereiht = {}, []
    monkeypatch.setattr("src.core.db.pool._get_pool", lambda: pytest.fail("Die Annahme fragt die echte Datenbank"))
    monkeypatch.setattr(open_jobs, "max_open_jobs", lambda: -1)
    monkeypatch.setattr(route.db, "get_provider", lambda pid: {"id": pid, "enabled": stand["client"] is not None})
    monkeypatch.setattr(tts_job_provider, "_there", lambda provider: stand["da"] and provider["enabled"])
    monkeypatch.setattr("src.dependencies.get_tts_client_for_provider", lambda pid, user_id=None: stand["client"])
    monkeypatch.setattr(route, "pick", lambda pid, stimmen: VoicePick(
        21 if stand["rueckfall"] else pid, ("onyx",) if stand["rueckfall"] else tuple(stimmen), stand["rueckfall"]))
    for name in ("enforce_open_jobs", "enforce_tool_burst", "enforce_quota"):
        monkeypatch.setattr(route, name, lambda *a, **k: None)
    monkeypatch.setattr(route.db, "create_job", lambda *a, **k: None)
    monkeypatch.setattr(route.db, "set_job_input_path", lambda *a, **k: None)
    monkeypatch.setattr(route.db, "set_job_celery_task_id", lambda *a, **k: None)
    monkeypatch.setattr(route, "save_queue_file_from_path", lambda uid, job, ext, pfad: "queue/in.txt")
    monkeypatch.setattr(route, "save_job_file", lambda uid, job, name, daten: abgelegt.__setitem__(name, daten))
    monkeypatch.setattr(tts_tasks, "run_tts", type("T", (), {"apply_async": staticmethod(
        lambda args=None, **k: eingereiht.append(args) or type("R", (), {"id": "task-1"})())})())
    return stand, abgelegt, eingereiht


async def _senden():
    return await route.text_to_speech(
        request=_Request(), file=None, text="Hallo Welt", voice_id="anna", speed=1.0,
        provider_id=30, voice_label="Anna", current_user={"user_id": 1}, locale="de")


async def test_ein_nicht_erreichbarer_anbieter_mit_rueckfall_nimmt_den_auftrag_an(annahme):
    """The choice itself is made only at start, until then the folder holds the person's choice."""
    _stand, abgelegt, eingereiht = annahme

    antwort = await _senden()

    assert antwort["job_uuid"]
    assert eingereiht[0][3:7] == ["anna", 1.0, 30, "Anna"]
    assert json.loads(abgelegt["tts_params.json"]) == {
        "voice_id": "anna", "voice_label": "Anna", "speed": 1.0, "provider_id": 30}


async def test_ein_ausgeschalteter_anbieter_mit_rueckfall_nimmt_den_auftrag_an(annahme):
    stand, _abgelegt, eingereiht = annahme
    stand["client"] = None

    await _senden()

    assert len(eingereiht) == 1


async def test_ohne_brauchbaren_rueckfall_lehnt_er_wie_bisher_ab(annahme):
    stand, _abgelegt, eingereiht = annahme
    stand["rueckfall"] = False

    with pytest.raises(HTTPException) as fehler:
        await _senden()

    assert fehler.value.status_code == 503
    assert eingereiht == []


async def test_ein_ausgeschalteter_anbieter_ohne_rueckfall_bleibt_nicht_gefunden(annahme):
    stand, _abgelegt, eingereiht = annahme
    stand["client"], stand["rueckfall"] = None, False

    with pytest.raises(HTTPException) as fehler:
        await _senden()

    assert fehler.value.status_code == 400
    assert eingereiht == []


async def test_ist_der_gewaehlte_da_fragt_er_den_rueckfall_gar_nicht(annahme, monkeypatch):
    stand, _abgelegt, eingereiht = annahme
    stand["da"] = True
    monkeypatch.setattr(route, "pick", lambda *a: pytest.fail("pick darf nicht laufen"))

    await _senden()

    assert len(eingereiht) == 1


async def test_die_annahme_sieht_den_gewaehlten_mit_den_augen_der_wahl(annahme):
    """A fresh probe of its own could contradict the choice's view and reject without reason."""
    stand, _abgelegt, eingereiht = annahme
    stand["da"], stand["rueckfall"] = True, False

    await _senden()

    assert len(eingereiht) == 1
