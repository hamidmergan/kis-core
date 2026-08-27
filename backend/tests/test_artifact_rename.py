"""Renaming a set, mind map and data table, checked against the statement."""

import pytest

from src.features.ai_assistant.repository import titles as repo


class _FakeCursor:
    def __init__(self, calls, rowcount):
        self._calls = calls
        self.rowcount = rowcount

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self._calls.append((" ".join(sql.split()), params))


class _FakeConn:
    def __init__(self, calls, rowcount):
        self._calls = calls
        self._rowcount = rowcount

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self, *a, **kw):
        return _FakeCursor(self._calls, self._rowcount)

    def commit(self):
        self._calls.append(("commit", None))


@pytest.fixture
def treffer(monkeypatch):
    calls = []
    monkeypatch.setattr(repo, "get_connection", lambda: _FakeConn(calls, 1))
    return calls


@pytest.fixture
def kein_treffer(monkeypatch):
    calls = []
    monkeypatch.setattr(repo, "get_connection", lambda: _FakeConn(calls, 0))
    return calls


def test_clean_title_trimmt_und_faltet_leerzeichen():
    assert repo.clean_title("  Zwei   Woerter \n") == "Zwei Woerter"


def test_clean_title_kuerzt_auf_die_obergrenze():
    assert len(repo.clean_title("x" * 500)) == repo.MAX_TITLE_LEN


def test_clean_title_vertraegt_none():
    assert repo.clean_title(None) == ""


@pytest.mark.parametrize(
    "kind,tabelle",
    [
        ("exercise_set", "aia_exercise_sets"),
        ("mindmap", "aia_mindmaps"),
        ("data_table", "aia_data_tables"),
    ],
)
def test_jede_art_trifft_ihre_tabelle(treffer, kind, tabelle):
    assert repo.update_artifact_title(kind, 5, 3, 7, "Neu") is True
    sql, params = treffer[0]
    assert f"UPDATE {tabelle}" in sql
    assert params == ("Neu", 5, 3, 7)


def test_die_bedingung_verlangt_person_und_kursraum(treffer):
    repo.update_artifact_title("mindmap", 5, 3, 7, "Neu")
    sql = treffer[0][0]
    assert "WHERE id = %s AND user_id = %s AND workspace_id = %s" in sql


def test_ohne_treffer_kommt_false(kein_treffer):
    assert repo.update_artifact_title("mindmap", 5, 3, 7, "Neu") is False


def test_unbekannte_art_wird_abgelehnt(treffer):
    with pytest.raises(KeyError):
        repo.update_artifact_title("workspace", 5, 3, 7, "Neu")


def test_es_wird_committet(treffer):
    repo.update_artifact_title("mindmap", 5, 3, 7, "Neu")
    assert ("commit", None) in treffer
