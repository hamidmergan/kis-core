"""Subprocesses of a screencast job: tracked while they run, gone afterwards."""

import pytest

from src.services.screencast import process


class _Proc:
    pid = 4711
    returncode = None

    def __init__(self, fehler=None):
        self.fehler = fehler

    def communicate(self, timeout=None):
        if self.fehler:
            raise self.fehler
        self.returncode = 0
        return b"aus", b""

    def poll(self):
        return self.returncode


def test_nach_dem_lauf_bleibt_kein_eintrag_des_auftrags_zurueck(monkeypatch):
    monkeypatch.setattr(process.subprocess, "Popen", lambda *a, **k: _Proc())
    ergebnis = process.run_proc(["ffmpeg"], timeout=5, job_uuid="job-1")
    assert ergebnis.stdout == "aus"
    assert "job-1" not in process._job_procs


def test_ein_abbruch_beim_warten_beendet_den_prozess(monkeypatch):
    """A time limit while waiting left ffmpeg running without anybody tracking it."""
    proc = _Proc(fehler=KeyboardInterrupt())
    beendet = []
    monkeypatch.setattr(process.subprocess, "Popen", lambda *a, **k: proc)
    monkeypatch.setattr(process, "_kill", beendet.append)
    with pytest.raises(KeyboardInterrupt):
        process.run_proc(["ffmpeg"], timeout=5, job_uuid="job-2")
    assert beendet == [proc]
    assert "job-2" not in process._job_procs
