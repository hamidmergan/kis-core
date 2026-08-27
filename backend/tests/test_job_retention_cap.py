"""Only the pool counts, and it now has to clear failures too."""

import pytest

from src.features.jobs.repository import _retention as vorrat
from src.features.jobs.repository import _crud as crud


def _job(nummer: int, status: str = "success") -> dict:
    return {"job_uuid": f"job-{nummer}", "user_id": 1, "status": status}


def _jobs(anzahl: int, status: str = "success") -> list[dict]:
    """Newest first, the way the database delivers them."""
    return [_job(n, status) for n in range(anzahl)]


# --- The pure selection rule -----------------------------------------------

def test_unter_der_grenze_faellt_nichts_raus():
    assert vorrat.select_jobs_to_evict(_jobs(20), cap=20) == []


def test_ueber_der_grenze_faellt_das_aelteste_raus():
    faellig = vorrat.select_jobs_to_evict(_jobs(23), cap=20)
    assert [j["job_uuid"] for j in faellig] == ["job-20", "job-21", "job-22"]


def test_fehlgeschlagene_jobs_zaehlen_mit_und_fliegen_raus():
    """Without this a user with nothing but failures would keep corpses forever."""
    faellig = vorrat.select_jobs_to_evict(_jobs(25, status="failed"), cap=20)
    assert len(faellig) == 5


@pytest.mark.parametrize("status", ["pending", "queued", "running", "awaiting_user"])
def test_laufende_jobs_werden_nie_geraeumt(status):
    """Otherwise the cleanup pulls the job out from under a user."""
    jobs = _jobs(20) + [_job(99, status=status)]
    assert vorrat.select_jobs_to_evict(jobs, cap=20) == []


def test_laufende_jobs_zaehlen_trotzdem_gegen_die_grenze():
    """A running job takes a slot, it is visible after all."""
    jobs = [{"job_uuid": "laeuft", "user_id": 1, "status": "running"}] + _jobs(20)
    faellig = vorrat.select_jobs_to_evict(jobs, cap=20)
    assert [j["job_uuid"] for j in faellig] == ["job-19"]


def test_die_grenze_ist_standardmaessig_der_vorrat_aus_limits():
    from src.limits import MAX_RESULT_FILES
    assert vorrat.select_jobs_to_evict(_jobs(MAX_RESULT_FILES + 1)) != []
    assert vorrat.select_jobs_to_evict(_jobs(MAX_RESULT_FILES)) == []


# --- Creating no longer sets a deadline ------------------------------------

class _FakeCursor:
    def __init__(self, calls):
        self._calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self._calls.append((sql, params))

    def fetchone(self):
        return None

    def fetchall(self):
        return []


class _FakeConn:
    def __init__(self, calls):
        self._calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self, **kwargs):
        return _FakeCursor(self._calls)

    def commit(self):
        pass


def test_ein_neuer_job_bekommt_kein_ablaufdatum(monkeypatch):
    calls: list[tuple] = []
    monkeypatch.setattr(crud, "get_connection", lambda: _FakeConn(calls))

    crud.create_job("u-1", 1, "translation", "datei.pdf")

    sql, params = calls[0]
    assert "expires_at" not in sql, "die Frist ist raus, die Spalte bleibt leer"
    assert not any(hasattr(p, "year") for p in params), "kein Datum in den Werten"


def test_die_frist_ist_als_konstante_verschwunden():
    """If it stays, someone will eventually reinstate it by accident."""
    import src.limits as limits
    assert not hasattr(limits, "JOB_RETENTION_HOURS")
