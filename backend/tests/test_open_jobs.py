"""The limit counts running jobs across all tools, parked ones excluded."""

import pytest
from fastapi import HTTPException

from src.services import open_jobs


@pytest.fixture
def zaehler(monkeypatch):
    """Returns how many jobs are currently working."""
    stand = {"n": 0, "grenze": 5}
    monkeypatch.setattr(open_jobs.db, "count_working_jobs", lambda uid, voice=None: stand["n"])
    monkeypatch.setattr(open_jobs, "max_open_jobs", lambda: stand["grenze"])
    return stand


def test_unter_der_grenze_geht_es_weiter(zaehler):
    zaehler["n"] = 4
    open_jobs.enforce_open_jobs(7, "de", "summary")


def test_auf_der_grenze_ist_schluss(zaehler):
    zaehler["n"] = 5
    with pytest.raises(HTTPException) as fehler:
        open_jobs.enforce_open_jobs(7, "de", "summary")
    assert fehler.value.status_code == 409


def test_minus_eins_laesst_alles_durch(zaehler):
    zaehler["grenze"] = -1
    zaehler["n"] = 999
    open_jobs.enforce_open_jobs(7, "de", "summary")


def test_die_abfrage_zaehlt_keine_wartenden(monkeypatch):
    """The status awaiting_user must not appear in the query at all."""
    import inspect
    from src.features.jobs.repository import _queries

    quelle = inspect.getsource(_queries.count_working_jobs)
    assert "awaiting_user" not in quelle.split('"""')[2]
    assert "'pending', 'running', 'queued'" in quelle


def test_praesentation_zaehlung_zaehlt_kein_fortsetzen(monkeypatch):
    """Continue (awaiting_user/paused) is idle and does not count as active for the one-job rule."""
    import inspect
    from src.features.jobs.repository import _queries

    quelle = inspect.getsource(_queries.count_active_jobs_for_tool)
    assert "awaiting_user" not in quelle.split('"""')[2]
    assert "paused" not in quelle.split('"""')[2]
    assert "'pending', 'running', 'queued', 'waiting_retry'" in quelle
