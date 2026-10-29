"""The evidence search only ranks seen pages, as an OR chain in the query."""
import time

import pytest

from src.features.ai_assistant.repository import chunks as repo


WS = 4243
_FRAGMENT = "c.source_id = %s"


class _FakeCursor:
    def __init__(self, calls):
        self._calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self._calls.append((sql, params))

    def fetchall(self):
        return []          # no hits -> the function stops after the fusion


class _FakeConn:
    def __init__(self, calls):
        self._calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self, **kwargs):
        return _FakeCursor(self._calls)


@pytest.fixture
def abfragen(monkeypatch):
    """Calls hybrid_search_chunks against a stub and returns the SQL calls."""
    # Preload the weight cache so the keyword arm is built.
    jetzt = time.monotonic()
    monkeypatch.setitem(repo._IDF_N_CACHE, WS, (jetzt, 1000))
    monkeypatch.setitem(repo._IDF_CACHE, (WS, "fragestunde"), (jetzt, 3.0))

    def _lauf(**kwargs):
        calls: list[tuple] = []
        monkeypatch.setattr(repo, "get_connection", lambda: _FakeConn(calls))
        repo.hybrid_search_chunks(WS, "Fragestunde", [0.1] * 2560, **kwargs)
        return [(sql, p) for sql, p in calls if "aia_chunks" in sql]

    return _lauf


def test_ohne_angabe_bleibt_die_abfrage_wie_bisher(abfragen):
    # The main retrieval still searches broadly, only the evidence search narrows.
    for sql, _params in abfragen():
        assert _FRAGMENT not in sql


def test_jeder_arm_der_suche_traegt_den_filter(abfragen):
    # Every arm has to carry the filter, otherwise one brings the pages back.
    treffer = [sql for sql, _p in abfragen(seen_pages={7: {5, 6}})
               if _FRAGMENT in sql]
    assert len(treffer) == 3


def test_pdf_quelle_nur_auf_ihren_gesehenen_seiten(abfragen):
    geprueft = 0
    for sql, params in abfragen(seen_pages={7: {6, 5}}):
        if _FRAGMENT not in sql:
            continue
        geprueft += 1
        # Source as a single value, pages as a list, exactly what the index can serve.
        assert "(c.source_id = %s AND c.page_number = ANY(%s))" in sql
        assert 7 in params
        assert [5, 6] in params
    assert geprueft == 3


def test_medienquelle_kommt_ganz_durch(abfragen):
    # Media have an empty page set and have to pass through completely.
    geprueft = 0
    for sql, params in abfragen(seen_pages={9: set()}):
        if _FRAGMENT not in sql:
            continue
        geprueft += 1
        assert 9 in params
        # No page condition for this source, otherwise every video fails.
        assert "(c.source_id = %s)" in sql
        assert not any(isinstance(p, list) for p in params)
    assert geprueft == 3


def test_quelle_ohne_eintrag_faellt_ganz_weg(abfragen):
    # A source that was not retrieved must not get a chip.
    geprueft = 0
    for sql, params in abfragen(seen_pages={7: {5}}):
        if _FRAGMENT not in sql:
            continue
        geprueft += 1
        assert 8 not in params
    assert geprueft == 3
