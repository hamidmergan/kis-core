"""Die Vertonung arbeitet in Etappen und reiht sich selbst wieder ein."""

from contextlib import contextmanager

import pytest

from src.features.podcast.schemas import Line, PodcastParams, Person
from src.tasks._stage import StageClock
from src.tasks.podcast_tasks import _render

UID = 7
JOB = "e" * 32


class _Store:
    """Auftragsordner im Speicher, merkt sich welche Beitraege vertont wurden."""

    def __init__(self, lines, params):
        self.lines = lines
        self.params = params
        self.vertont = []

    def load_params(self, uid, job):
        return self.params

    def load_lines(self, uid, job):
        return self.lines

    def load_voiced(self, uid, job):
        return {}

    def load_pin(self, uid, job):
        return {}

    def pinned_voice(self, pin, provider_id, voice_id):
        return provider_id, voice_id

    def needs_voice(self, line, voiced, voice_id, speed, provider_id=0, chosen_provider_id=None):
        return line.id not in self.vertont

    def has_line_audio(self, uid, job, line_id):
        return line_id in self.vertont

    def save_line_audio(self, uid, job, line_id, data):
        self.vertont.append(line_id)

    def fingerprint(self, line, voice_id, speed, provider_id=0):
        return {"text": line.text}

    def save_voiced(self, uid, job, voiced):
        pass

    def get_line_audio(self, uid, job, line_id):
        return b"ton"

    def save_transcript(self, uid, job, text):
        pass


class _Db:
    def __init__(self):
        self.status = []
        self.claim = ("running", 0)
        self.job = {"progress": None}

    def update_job_status(self, job_uuid, status, progress=None, error_message=None):
        self.status.append((status, progress))

    def reset_job_to_awaiting(self, job_uuid):
        self.status.append(("awaiting_user", None))

    def job_claim(self, job_uuid):
        return self.claim

    def touch_job_heartbeat(self, job_uuid):
        pass

    def get_job(self, job_uuid):
        return self.job

    def get_provider(self, pid):
        return {"name": "Anbieter"}


class _Task:
    """Faengt auf, womit sich die Etappe selbst wieder einreiht."""

    def __init__(self):
        self.aufrufe = []

    def apply_async(self, args=None, **kwargs):
        self.aufrufe.append(args)
        return type("R", (), {"id": "task-2"})()


def _lines(n):
    return [Line(id=f"l{i}", speaker=0, text=f"Text {i}") for i in range(n)]


@pytest.fixture
def umgebung(monkeypatch):
    db = _Db()
    task = _Task()
    anlaeufe = []
    monkeypatch.setattr(_render, "db", db)
    monkeypatch.setattr("src.database.get_provider", db.get_provider)
    monkeypatch.setattr(_render, "assert_not_cancelled", lambda job: None)
    monkeypatch.setattr(_render, "still_mine", lambda job, token: db.claim == ("running", token))
    monkeypatch.setattr(_render, "attempt_failed",
                        lambda job, meldung, **k: anlaeufe.append(meldung) or "waiting_retry")
    monkeypatch.setattr(_render, "continue_stage",
                        lambda selbst, args, job: task.apply_async(args=args))
    monkeypatch.setattr(_render, "tts_client", lambda pid, user_id=None: object())
    monkeypatch.setattr(_render, "anbieter_und_modelle", lambda pids, art: {})
    @contextmanager
    def _stumm(*args, **kwargs):
        yield {}

    monkeypatch.setattr(_render, "job_heartbeat", _stumm)
    monkeypatch.setattr(_render, "messe", _stumm)
    monkeypatch.setattr(_render, "montage",
                        type("M", (), {"kleben": staticmethod(lambda s, j: (b"mp3", 12.0))}))
    monkeypatch.setattr(_render, "save_result_file", lambda uid, job, endung, daten: "p.mp3")
    monkeypatch.setattr(_render, "save_result_meta", lambda uid, job, meta: None)
    monkeypatch.setattr(_render, "load_result_meta", lambda uid, job: {})
    monkeypatch.setattr(_render, "save_result_and_evict", lambda uid, job, pfad, name: None)
    return db, task, anlaeufe


def _params():
    return PodcastParams(persons=[Person(name="A", voice_id="v0")])


def test_eine_abgelaufene_uhr_reiht_den_rest_als_neue_etappe_ein(umgebung, monkeypatch):
    db, task, _ = umgebung
    store = _Store(_lines(4), _params())
    monkeypatch.setattr(_render, "store", store)
    # Nach zwei Beitraegen ist die Etappe vorbei.
    uhr = iter([False, False, True, True, True, True])
    monkeypatch.setattr(_render, "StageClock",
                        lambda *a, **k: type("C", (), {"over": staticmethod(lambda: next(uhr)),
                                                       "spent": staticmethod(lambda: 0.0)})())
    monkeypatch.setattr(_render, "_mit_wiederholung",
                        lambda *a, **k: b"ton")

    _render.run_podcast_render(JOB, UID, "de", 1, 0)

    assert len(task.aufrufe) == 1
    assert task.aufrufe[0] == [JOB, UID, "de", 2, 0]
    assert len(store.vertont) == 2


def test_die_naechste_etappe_laeuft_nicht_auf_erfolg(umgebung, monkeypatch):
    db, _, _ = umgebung
    monkeypatch.setattr(_render, "store", _Store(_lines(4), _params()))
    uhr = iter([False, True, True, True, True, True])
    monkeypatch.setattr(_render, "StageClock",
                        lambda *a, **k: type("C", (), {"over": staticmethod(lambda: next(uhr)),
                                                       "spent": staticmethod(lambda: 0.0)})())
    monkeypatch.setattr(_render, "_mit_wiederholung", lambda *a, **k: b"ton")

    _render.run_podcast_render(JOB, UID, "de", 1, 0)

    assert "success" not in [s for s, _ in db.status]


def test_ohne_rest_wird_montiert_und_fertig_gemeldet(umgebung, monkeypatch):
    db, task, _ = umgebung
    monkeypatch.setattr(_render, "store", _Store(_lines(2), _params()))
    monkeypatch.setattr(_render, "_mit_wiederholung", lambda *a, **k: b"ton")

    _render.run_podcast_render(JOB, UID, "de", 1, 0)

    assert task.aufrufe == []
    assert db.status[-1][0] == "success"


def test_ein_anbieterfehler_zaehlt_als_anlauf_statt_fehlgeschlagen(umgebung, monkeypatch):
    db, _, anlaeufe = umgebung
    monkeypatch.setattr(_render, "store", _Store(_lines(2), _params()))

    def kaputt(*a, **k):
        raise RuntimeError("Anbieter weg")

    monkeypatch.setattr(_render, "_mit_wiederholung", kaputt)

    with pytest.raises(RuntimeError):
        _render.run_podcast_render(JOB, UID, "de", 1, 0)

    assert len(anlaeufe) == 1
    assert "failed" not in [s for s, _ in db.status]


def test_ein_voller_anbieter_wird_als_voll_gemeldet(umgebung, monkeypatch):
    """Lasttest 26.09.: myLab antwortete mit 500, der Podcast verbrauchte dafür seine Anläufe."""
    monkeypatch.setattr(_render, "store", _Store(_lines(2), _params()))
    gemeldet = []
    monkeypatch.setattr(_render, "attempt_failed",
                        lambda job, meldung, **k: gemeldet.append(k) or "waiting_retry")

    def voll(*a, **k):
        raise RuntimeError("TTS API error (500): Internal Server Error")

    monkeypatch.setattr(_render, "_mit_wiederholung", voll)

    with pytest.raises(RuntimeError):
        _render.run_podcast_render(JOB, UID, "de", 1, 0)

    assert gemeldet == [{"busy": True}]


def test_eine_fremd_uebernommene_etappe_schreibt_nichts(umgebung, monkeypatch):
    db, task, _ = umgebung
    store = _Store(_lines(2), _params())
    monkeypatch.setattr(_render, "store", store)
    monkeypatch.setattr(_render, "_mit_wiederholung", lambda *a, **k: b"ton")
    db.claim = ("running", 5)

    _render.run_podcast_render(JOB, UID, "de", 1, 0)

    assert db.status == []
    assert store.vertont == []
    assert task.aufrufe == []


def test_die_zweite_etappe_nimmt_das_behalten_aus_dem_fortschritt(umgebung, monkeypatch):
    db, _, _ = umgebung
    store = _Store(_lines(3), _params())
    store.vertont = ["l0"]
    monkeypatch.setattr(_render, "store", store)
    monkeypatch.setattr(_render, "_mit_wiederholung", lambda *a, **k: b"ton")
    # Die erste Etappe hatte nichts behalten, l0 kam erst in diesem Lauf dazu.
    db.job = {"progress": '{"behalten": []}'}

    _render.run_podcast_render(JOB, UID, "de", 2, 0)

    tts = [p for s, p in db.status if p and p.get("step") == "tts"]
    assert tts[0]["behalten"] == []
    assert tts[0]["total"] == 3


def test_die_wiederholungsleiter_haelt_an_wenn_die_etappe_vorbei_ist():
    versuche = []

    def sprich(client, text, voice_id, sprache, tempo):
        versuche.append(text)
        raise RuntimeError("Anbieter weg")

    import src.tasks.podcast_tasks._render as modul
    echt = modul._sprich
    modul._sprich = sprich
    try:
        with pytest.raises(RuntimeError):
            modul._mit_wiederholung(None, "Text", "v", "de", 1.0, "", StageClock(seconds=0))
    finally:
        modul._sprich = echt

    # Nur der erste Versuch, danach greift die Uhr vor der Pause.
    assert len(versuche) == 1
