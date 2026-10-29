"""Text to speech works in stages and skips finished chunks."""

import json

import pytest

from src.services.tts_job_provider import VoicePick
from src.tasks import tts_tasks

JOB = "f" * 32
UID = 7


class _Ablage:
    """Job folder as a dict, queried by name like the real storage."""

    def __init__(self, vorhanden=()):
        self.dateien = {name: b"alt" for name in vorhanden}

    def get(self, uid, job, name):
        if name not in self.dateien:
            raise FileNotFoundError(name)
        return self.dateien[name]

    def put(self, uid, job, name, daten):
        self.dateien[name] = daten


class _Client:
    """Counts which texts the provider was actually called for."""

    def __init__(self):
        self.gesprochen = []

    def synthesize_chunk(self, text, voice_id="", speed=1.0, language="de"):
        self.gesprochen.append(text)
        return b"ton"


class _Db:
    def __init__(self):
        self.status = []
        self.claim = ("running", 0)

    def update_job_status(self, job_uuid, status, progress=None, error_message=None):
        self.status.append((status, progress))

    def get_job(self, job_uuid):
        return {"user_id": UID, "creator_locale": "de"}

    def job_claim(self, job_uuid):
        return self.claim

    def touch_job_heartbeat(self, job_uuid):
        pass


class _Task:
    def __init__(self):
        self.aufrufe = []

    def apply_async(self, args=None, **kwargs):
        self.aufrufe.append(args)
        return type("R", (), {"id": "task-2"})()


@pytest.fixture
def umgebung(monkeypatch):
    db, ablage, client, task = _Db(), _Ablage(), _Client(), _Task()
    anlaeufe = []
    monkeypatch.setattr(tts_tasks, "db", db)
    monkeypatch.setattr(tts_tasks, "get_job_file", ablage.get)
    monkeypatch.setattr(tts_tasks, "save_job_file", ablage.put)
    monkeypatch.setattr(tts_tasks, "job_file_exists", lambda uid, job, name: name in ablage.dateien)
    # The chosen provider is there, the fallback tests set their own choice.
    monkeypatch.setattr(tts_tasks, "pick", lambda pid, stimmen: VoicePick(pid, tuple(stimmen), False))
    monkeypatch.setattr(tts_tasks, "get_file", lambda pfad: b"egal")
    monkeypatch.setattr(tts_tasks, "delete_file", lambda pfad: None)
    monkeypatch.setattr(tts_tasks, "save_result_file", lambda uid, job, endung, daten: "p.mp3")
    monkeypatch.setattr(tts_tasks, "save_result_and_evict", lambda uid, job, pfad, name: None)
    monkeypatch.setattr(tts_tasks, "_stamped_with_ai_notice", lambda daten: daten)
    monkeypatch.setattr(tts_tasks, "still_mine", lambda job, token: db.claim == ("running", token))
    def anlauf(job_uuid, meldung, **k):
        anlaeufe.append(meldung)
        return "waiting_retry"

    monkeypatch.setattr(tts_tasks, "attempt_failed", anlauf)
    # Generic errors take the shared path, it has its own handle on the service.
    from src.services import job_recovery
    monkeypatch.setattr(job_recovery, "attempt_failed", anlauf)
    monkeypatch.setattr(tts_tasks, "continue_stage",
                        lambda selbst, args, job: task.apply_async(args=args))
    monkeypatch.setattr("src.utils.text_extraction.EXTRACTORS",
                        {".txt": lambda inhalt: "Eins. Zwei. Drei."})
    monkeypatch.setattr("src.dependencies.get_tts_client_for_provider", lambda pid, user_id=None: client)
    monkeypatch.setattr("src.dependencies._voice_language_for", lambda pid, vid: "de")
    monkeypatch.setattr("src.services.openai_compat_tts._split_text",
                        lambda text: ["Eins.", "Zwei.", "Drei."])
    return db, ablage, client, task, anlaeufe


def _lauf(versuch=0):
    tts_tasks.run_tts(JOB, "ein.txt", "ein.txt", "v1", 1.0, 2, "Stimme", versuch)


def test_die_stimmeinstellungen_liegen_vor_dem_ersten_anbieteraufruf_im_ordner(umgebung):
    _db, ablage, client, _task, _a = umgebung
    _lauf()
    gespeichert = json.loads(ablage.dateien["tts_params.json"])
    assert gespeichert["voice_id"] == "v1"
    assert gespeichert["provider_id"] == 2


def test_fertige_stuecke_kosten_den_anbieter_nichts(umgebung):
    _db, ablage, client, _task, _a = umgebung
    ablage.dateien["chunk_000.mp3"] = b"schon da"
    ablage.dateien["chunk_001.mp3"] = b"schon da"

    _lauf()

    assert client.gesprochen == ["Drei."]


def test_eine_abgelaufene_uhr_reiht_den_rest_als_neue_etappe_ein(umgebung, monkeypatch):
    _db, _ablage, client, task, _a = umgebung
    uhr = iter([False, True, True, True])
    monkeypatch.setattr(tts_tasks, "StageClock",
                        lambda *a, **k: type("C", (), {"over": staticmethod(lambda: next(uhr))})())

    _lauf()

    assert client.gesprochen == ["Eins."]
    assert task.aufrufe == [[JOB, "ein.txt", "ein.txt", "v1", 1.0, 2, "Stimme", 0]]


def test_ein_netzfehler_zaehlt_als_anlauf_ohne_celery_wiederholung(umgebung, monkeypatch):
    _db, _ablage, client, _task, anlaeufe = umgebung

    def kaputt(*a, **k):
        raise RuntimeError("Anbieter weg")

    monkeypatch.setattr(client, "synthesize_chunk", kaputt)

    with pytest.raises(RuntimeError):
        _lauf()

    assert anlaeufe == ["Anbieter weg"]


def test_eine_fremd_uebernommene_etappe_spricht_nichts(umgebung):
    db, _ablage, client, task, _a = umgebung
    db.claim = ("running", 4)

    _lauf(versuch=0)

    assert client.gesprochen == []
    assert task.aufrufe == []
