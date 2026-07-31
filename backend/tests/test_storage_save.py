"""Ablegen im Speicher: jede Funktion schreibt an ihren Platz und meldet ihn zurueck.

Die Funktionen hatten alle denselben Rumpf, nur mit einem anderen Schluessel.
Diese Tests halten fest, was jede von ihnen tut, damit das Zusammenziehen
nichts verschiebt. Zwei Dinge sind leicht zu uebersehen: mit S3 kommt der
Schluessel zurueck, ohne S3 der volle Pfad, und der Ordner muss angelegt
werden, bevor geschrieben wird.
"""

import json

import pytest

from src import storage


@pytest.fixture
def s3(monkeypatch):
    """Speicher mit S3: merkt sich, was abgelegt wurde."""
    abgelegt: dict[str, bytes] = {}
    hochgeladen: dict[str, str] = {}

    class _FakeS3:
        def put_object(self, Bucket=None, Key=None, Body=None, **kw):
            abgelegt[Key] = Body

        def upload_file(self, local_path, Bucket, Key, **kw):
            hochgeladen[Key] = local_path

    monkeypatch.setattr(storage, "USE_S3", True)
    monkeypatch.setattr(storage, "_s3", lambda: _FakeS3())
    return abgelegt, hochgeladen


# ─── Ohne S3: voller Pfad zurueck, Ordner wird angelegt ────────────────────

def test_jede_bytes_funktion_schreibt_an_ihren_platz(lokal):
    job = lokal / "users/7/jobs/j1"

    assert storage.save_queue_file(7, "j1", ".pdf", b"eingang") == str(job / "input.pdf")
    assert storage.save_result_file(7, "j1", ".mp4", b"ausgang") == str(job / "output.mp4")
    assert storage.save_job_file(7, "j1", "notiz.txt", b"notiz") == str(job / "notiz.txt")
    assert storage.save_result_json(7, "j1", {"a": 1}) == str(job / "result.json")

    assert (job / "input.pdf").read_bytes() == b"eingang"
    assert (job / "output.mp4").read_bytes() == b"ausgang"
    assert (job / "notiz.txt").read_bytes() == b"notiz"
    assert json.loads((job / "result.json").read_text()) == {"a": 1}


def test_meta_und_pptx_schreiben_ohne_rueckgabe(lokal):
    assert storage.save_result_meta(7, "j1", {"b": 2}) is None
    assert storage.save_pptx_tmp("f1", b"pptx") is None

    assert json.loads((lokal / "users/7/jobs/j1/meta.json").read_text()) == {"b": 2}
    assert (lokal / "tmp/pptx/f1.pptx").read_bytes() == b"pptx"


def test_jede_pfad_funktion_kopiert_an_ihren_platz(lokal, tmp_path):
    quelle = tmp_path / "hochgeladen.bin"
    quelle.write_bytes(b"inhalt")
    job = lokal / "users/7/jobs/j1"

    assert storage.save_queue_file_from_path(7, "j1", ".mp4", str(quelle)) == str(job / "input.mp4")
    assert storage.save_job_file_from_path(7, "j1", "roh.bin", str(quelle)) == str(job / "roh.bin")
    assert storage.save_aia_source_from_path(7, "w1", "s1", ".pdf", str(quelle)) == str(
        lokal / "users/7/aia/workspaces/w1/sources/s1.pdf"
    )

    assert (job / "input.mp4").read_bytes() == b"inhalt"
    assert (job / "roh.bin").read_bytes() == b"inhalt"
    assert (lokal / "users/7/aia/workspaces/w1/sources/s1.pdf").read_bytes() == b"inhalt"


def test_der_ordner_wird_angelegt_falls_er_fehlt(lokal):
    """Bei einem frischen Job gibt es den Ordner noch nicht."""
    assert not (lokal / "users/9").exists()

    storage.save_queue_file(9, "neu", ".txt", b"x")

    assert (lokal / "users/9/jobs/neu/input.txt").read_bytes() == b"x"


# ─── Mit S3: Schluessel zurueck, kein Pfad ─────────────────────────────────

def test_mit_s3_kommt_der_schluessel_zurueck(s3):
    abgelegt, _ = s3

    assert storage.save_queue_file(7, "j1", ".pdf", b"eingang") == "users/7/jobs/j1/input.pdf"
    assert storage.save_result_file(7, "j1", ".mp4", b"a") == "users/7/jobs/j1/output.mp4"
    assert storage.save_job_file(7, "j1", "notiz.txt", b"n") == "users/7/jobs/j1/notiz.txt"
    assert storage.save_result_json(7, "j1", {"a": 1}) == "users/7/jobs/j1/result.json"
    assert abgelegt["users/7/jobs/j1/input.pdf"] == b"eingang"
    assert json.loads(abgelegt["users/7/jobs/j1/result.json"]) == {"a": 1}


def test_mit_s3_werden_pfad_funktionen_hochgeladen_statt_gelesen(s3):
    _, hochgeladen = s3

    assert storage.save_queue_file_from_path(7, "j1", ".mp4", "/tmp/x") == "users/7/jobs/j1/input.mp4"
    assert storage.save_aia_source_from_path(7, "w1", "s1", ".pdf", "/tmp/x") == (
        "users/7/aia/workspaces/w1/sources/s1.pdf"
    )
    assert hochgeladen == {
        "users/7/jobs/j1/input.mp4": "/tmp/x",
        "users/7/aia/workspaces/w1/sources/s1.pdf": "/tmp/x",
    }


def test_mit_s3_landet_meta_unter_seinem_schluessel(s3):
    abgelegt, _ = s3

    storage.save_result_meta(7, "j1", {"b": 2})
    storage.save_pptx_tmp("f1", b"pptx")

    assert json.loads(abgelegt["users/7/jobs/j1/meta.json"]) == {"b": 2}
    assert abgelegt["tmp/pptx/f1.pptx"] == b"pptx"
