"""Die Grenze pro Person gilt fuer jeden Dienst und haelt auch zwei gleichzeitige Starts auf."""

import ast
import os
import pathlib
import threading
import uuid

import pytest
from fastapi import HTTPException

from src.features.jobs.repository import _crud
from src.services import open_jobs

ROUTES = pathlib.Path(__file__).resolve().parents[1] / "src" / "routes"


class _Cursor:
    def __init__(self, log, working):
        self.log, self.working = log, working

    def execute(self, sql, params=None):
        self.log.append((" ".join(sql.split()), params))

    def fetchone(self):
        return (self.working,)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class _Conn:
    def __init__(self, log, working):
        self.log, self.working = log, working

    def cursor(self, *a, **k):
        return _Cursor(self.log, self.working)

    def commit(self):
        self.log.append(("COMMIT", None))

    def rollback(self):
        self.log.append(("ROLLBACK", None))

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


@pytest.fixture
def fake_db(monkeypatch):
    def _make(working):
        log = []
        monkeypatch.setattr(_crud, "get_connection", lambda: _Conn(log, working))
        monkeypatch.setattr(_crud, "count_started", lambda cur, tool: None)
        return log
    return _make


def test_auf_der_grenze_wird_kein_auftrag_angelegt(fake_db):
    log = fake_db(working=2)
    with pytest.raises(_crud.TooManyOpenJobs):
        _crud.create_job("u1", 7, "summary", "a.pdf", limit=2)
    assert not any(sql.startswith("INSERT INTO jobs") for sql, _ in log)
    assert ("COMMIT", None) not in log


def test_unter_der_grenze_wird_angelegt(fake_db):
    log = fake_db(working=1)
    _crud.create_job("u1", 7, "summary", "a.pdf", limit=2)
    assert any(sql.startswith("INSERT INTO jobs") for sql, _ in log)
    assert ("COMMIT", None) in log


def test_erst_sperren_dann_zaehlen_dann_anlegen(fake_db):
    """Zwei Tabs derselben Person warten aufeinander, bevor sie zaehlen."""
    log = fake_db(working=0)
    _crud.create_job("u1", 7, "summary", "a.pdf", limit=2)
    sqls = [sql for sql, _ in log]
    sperre = next(i for i, s in enumerate(sqls) if "pg_advisory_xact_lock" in s)
    zaehlen = next(i for i, s in enumerate(sqls) if s.startswith("SELECT COUNT(*) FROM jobs"))
    anlegen = next(i for i, s in enumerate(sqls) if s.startswith("INSERT INTO jobs"))
    assert sperre < zaehlen < anlegen
    assert 7 in log[sperre][1]


def test_minus_eins_zaehlt_gar_nicht(fake_db):
    log = fake_db(working=999)
    _crud.create_job("u1", 7, "summary", "a.pdf", limit=-1)
    assert not any("pg_advisory_xact_lock" in sql for sql, _ in log)
    assert any(sql.startswith("INSERT INTO jobs") for sql, _ in log)


def test_der_dienst_meldet_409_mit_dem_bekannten_text(monkeypatch):
    def _voll(*a, **k):
        raise _crud.TooManyOpenJobs()
    monkeypatch.setattr(open_jobs.db, "create_job", _voll)
    monkeypatch.setattr(open_jobs, "max_open_jobs", lambda: 2)
    with pytest.raises(HTTPException) as fehler:
        open_jobs.create_counted_job("u1", 7, "summary", "a.pdf", locale="de")
    assert fehler.value.status_code == 409
    assert "zu viele Aufträge" in fehler.value.detail


def test_der_dienst_reicht_die_grenze_aus_dem_admin_weiter(monkeypatch):
    gesehen = {}
    monkeypatch.setattr(open_jobs.db, "create_job", lambda *a, **k: gesehen.update(k))
    monkeypatch.setattr(open_jobs, "max_open_jobs", lambda: 2)
    open_jobs.create_counted_job("u1", 7, "summary", "a.pdf", locale="de")
    assert gesehen["limit"] == 2


def _ruft_auf(baum, name):
    for knoten in ast.walk(baum):
        if isinstance(knoten, ast.Call):
            f = knoten.func
            if (isinstance(f, ast.Attribute) and f.attr == name) or (isinstance(f, ast.Name) and f.id == name):
                return True
    return False


def test_keine_route_legt_ungezaehlt_an():
    """Jeder Dienst legt seinen Auftrag ueber die gezaehlte Stelle an, auch die Praesentation."""
    direkt = []
    for datei in ROUTES.rglob("*.py"):
        baum = ast.parse(datei.read_text())
        for knoten in ast.walk(baum):
            if (isinstance(knoten, ast.Call) and isinstance(knoten.func, ast.Attribute)
                    and knoten.func.attr == "create_job"
                    and isinstance(knoten.func.value, ast.Name) and knoten.func.value.id == "db"):
                direkt.append(f"{datei.relative_to(ROUTES)}:{knoten.lineno}")
    assert direkt == []


def test_praesentation_prueft_die_grenze_vor_dem_lesen():
    baum = ast.parse((ROUTES / "praesentation" / "start.py").read_text())
    assert _ruft_auf(baum, "enforce_open_jobs")


@pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="braucht die echte Datenbank")
def test_zwei_gleichzeitige_starts_ueberschreiten_die_grenze_nicht():
    """Zwei Tabs starten im selben Moment, bei Grenze 1 kommt nur einer durch."""
    from src.core.db.pool import get_connection

    person = 900_000_000 + uuid.uuid4().int % 1_000_000
    start = threading.Barrier(2)
    ergebnisse = []

    def _starten():
        start.wait()
        try:
            _crud.create_job(uuid.uuid4().hex, person, "summary", "a.pdf", limit=1)
            ergebnisse.append("angelegt")
        except _crud.TooManyOpenJobs:
            ergebnisse.append("abgelehnt")

    try:
        faeden = [threading.Thread(target=_starten) for _ in range(2)]
        for f in faeden:
            f.start()
        for f in faeden:
            f.join(10)
        assert sorted(ergebnisse) == ["abgelehnt", "angelegt"]
    finally:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM jobs WHERE user_id = %s", (person,))
            conn.commit()


def _funktion(datei, name):
    baum = ast.parse((ROUTES / datei).read_text())
    return next(k for k in ast.walk(baum) if isinstance(k, (ast.FunctionDef, ast.AsyncFunctionDef)) and k.name == name)


@pytest.mark.parametrize("datei, name", [
    ("screencast/render.py", "screencast_render"),
    ("podcast/render.py", "start_render"),
    ("praesentation/outline.py", "start_build"),
    ("praesentation/slides.py", "regen_image"),
    ("praesentation/slides.py", "insert_slide"),
    ("praesentation/slides.py", "finalize"),
    ("jobs/_retry.py", "retry_job"),
])
def test_wer_einen_wartenden_auftrag_fortsetzt_zaehlt_mit(datei, name):
    """Lauf 15: ein geparkter Screencast zählte nicht, danach kamen zwei neue und dann das Vertonen, also drei."""
    assert _ruft_auf(_funktion(datei, name), "enforce_open_jobs")


# ─── Dienste mit Stimme zählen getrennt ───────────────────────────────────


def test_ein_dienst_ohne_stimme_zaehlt_nur_seinesgleichen(fake_db):
    """Lauf 15: Podcast und Text in Audio warteten auf Stimmen, Zusammenfassungen wurden bis zu 47 Mal abgewiesen."""
    log = fake_db(working=0)
    _crud.create_job("u1", 7, "summary", "a.pdf", limit=2)
    zaehlen = next((sql, p) for sql, p in log if sql.startswith("SELECT COUNT(*) FROM jobs"))
    assert "tool = ANY(%s)" in zaehlen[0]
    assert zaehlen[1][-1] is False


def test_ein_dienst_mit_stimme_zaehlt_nur_seinesgleichen(fake_db):
    log = fake_db(working=0)
    _crud.create_job("u1", 7, "tts", "a.txt", limit=2)
    zaehlen = next((sql, p) for sql, p in log if sql.startswith("SELECT COUNT(*) FROM jobs"))
    assert zaehlen[1][-1] is True


def test_zu_den_stimmen_gehoeren_text_in_audio_podcast_und_screencast():
    from src.features.jobs.repository._queries import VOICE_TOOLS

    assert VOICE_TOOLS == {"tts", "podcast", "screencast_translate", "screencast_render"}


def test_die_pruefung_im_formular_fragt_die_gruppe_des_dienstes(monkeypatch):
    gefragt = []
    monkeypatch.setattr(open_jobs.db, "count_working_jobs", lambda uid, voice=None: gefragt.append(voice) or 0)
    monkeypatch.setattr(open_jobs, "max_open_jobs", lambda: 2)
    open_jobs.enforce_open_jobs(7, "de", "podcast")
    open_jobs.enforce_open_jobs(7, "de", "summary")
    assert gefragt == [True, False]


@pytest.mark.skipif(not os.environ.get("DATABASE_URL"), reason="braucht die echte Datenbank")
def test_eine_stimme_haelt_keine_zusammenfassung_auf():
    from src.core.db.pool import get_connection

    person = 900_000_000 + uuid.uuid4().int % 1_000_000
    try:
        _crud.create_job(uuid.uuid4().hex, person, "podcast", "p", limit=1)
        _crud.create_job(uuid.uuid4().hex, person, "summary", "s", limit=1)
        with pytest.raises(_crud.TooManyOpenJobs):
            _crud.create_job(uuid.uuid4().hex, person, "tts", "t", limit=1)
        with pytest.raises(_crud.TooManyOpenJobs):
            _crud.create_job(uuid.uuid4().hex, person, "translation", "u", limit=1)
    finally:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM jobs WHERE user_id = %s", (person,))
            conn.commit()
