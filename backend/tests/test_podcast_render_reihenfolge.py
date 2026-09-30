"""Der Fortschritt zeigt Beitraege nur der Reihe nach, auch wenn sie verkehrt fertig werden."""

import threading
from contextlib import contextmanager

import pytest

from src.features.podcast.schemas import Line, PodcastParams, Person
from src.tasks.podcast_tasks import _render

UID = 7
JOB = "d" * 32


class _Store:
    """Job folder in memory, with a say over which contributions are already voiced."""

    def __init__(self, lines, params, behalten=()):
        self.lines = lines
        self.params = params
        self.behalten = set(behalten)
        self.transkript = ""

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
        return line.id not in self.behalten

    def has_line_audio(self, uid, job, line_id):
        return line_id in self.behalten

    def save_line_audio(self, uid, job, line_id, data):
        pass

    def fingerprint(self, line, voice_id, speed, provider_id=0):
        return {"text": line.text}

    def save_voiced(self, uid, job, voiced):
        pass

    def get_line_audio(self, uid, job, line_id):
        return b"ton"

    def save_transcript(self, uid, job, text):
        self.transkript = text


class _Db:
    """Keeps every published progress so the order can be read afterwards."""

    def __init__(self):
        self.stand = []
        self.claim = ("running", 0)

    def update_job_status(self, job_uuid, status, progress=None, error_message=None):
        if progress and progress.get("step") == "tts":
            self.stand.append(list(progress["fertig"]))

    def reset_job_to_awaiting(self, job_uuid):
        pass

    def job_claim(self, job_uuid):
        return self.claim

    def touch_job_heartbeat(self, job_uuid):
        pass

    def get_provider(self, pid):
        return {"name": "Anbieter"}


def _params(n=3):
    return PodcastParams(persons=[Person(name=f"P{i}", voice_id=f"v{i}") for i in range(n)])


def _lines(texte):
    return [Line(id=f"l{i}", speaker=i % 2, text=t) for i, t in enumerate(texte)]


@pytest.fixture
def umgebung(monkeypatch):
    """Everything around the voicing is faked, only the ordering stays real."""
    db = _Db()
    monkeypatch.setattr(_render, "db", db)
    monkeypatch.setattr("src.database.get_provider", db.get_provider)
    monkeypatch.setattr(_render, "assert_not_cancelled", lambda job: None)
    monkeypatch.setattr(_render, "still_mine", lambda job, token: True)
    monkeypatch.setattr(_render, "attempt_failed", lambda job, meldung, **k: "waiting_retry")
    monkeypatch.setattr(_render, "tts_client", lambda pid, user_id=None: object())
    monkeypatch.setattr(_render, "anbieter_und_modelle", lambda pids, art: {})
    monkeypatch.setattr(_render, "job_heartbeat", lambda job: contextmanager(lambda: iter([None]))())
    monkeypatch.setattr(_render, "messe", contextmanager(lambda uid, job, name: iter([{}])))
    monkeypatch.setattr(_render, "montage",
                        type("M", (), {"kleben": staticmethod(lambda s, p, j: (b"mp3", 12.0))}))
    monkeypatch.setattr(_render, "save_result_file", lambda uid, job, endung, daten: "p.mp3")
    monkeypatch.setattr(_render, "save_result_meta", lambda uid, job, meta: None)
    monkeypatch.setattr(_render, "load_result_meta", lambda uid, job: {})
    monkeypatch.setattr(_render, "save_result_and_evict", lambda uid, job, pfad, name: None)
    return db


def test_verkehrt_fertig_wird_trotzdem_der_reihe_nach_gezeigt(umgebung, monkeypatch):
    lines = _lines(["0", "1", "2"])
    monkeypatch.setattr(_render, "store", _Store(lines, _params()))
    # Contribution 2 finishes first, then 1, then 0: the order is fully reversed.
    ereignisse = {t: threading.Event() for t in ("1", "2")}

    def vertonen(client, text, voice_id, sprache, tempo, *rest):
        if text == "2":
            ereignisse["2"].set()
        if text == "1":
            assert ereignisse["2"].wait(5)
            ereignisse["1"].set()
        if text == "0":
            assert ereignisse["1"].wait(5)
        return b"ton"

    monkeypatch.setattr(_render, "_mit_wiederholung", vertonen)

    _render.run_podcast_render(JOB, UID)

    for gezeigt in umgebung.stand:
        assert gezeigt == list(range(len(gezeigt))), f"Luecke im Fortschritt: {gezeigt}"
    assert umgebung.stand[-1] == [0, 1, 2]


def test_behaltene_beitraege_sind_von_anfang_an_zu_hoeren(umgebung, monkeypatch):
    lines = _lines(["0", "1", "2"])
    monkeypatch.setattr(_render, "store", _Store(lines, _params(), behalten={"l0", "l2"}))
    monkeypatch.setattr(_render, "_mit_wiederholung",
                        lambda client, text, voice_id, sprache, tempo, *rest: b"ton")

    _render.run_podcast_render(JOB, UID)

    assert umgebung.stand[0] == [0, 2]
    assert umgebung.stand[-1] == [0, 1, 2]
