"""Die Mindmap-Liste zeigt den eigenen Titel, wenn es einen gibt.

Ohne den COALESCE saehen umbenannte Mindmaps in der Liste weiter nach ihrem
Wurzelknoten aus, obwohl der neue Name schon in der Spalte steht.

Keine echte Datenbank: geprueft wird die abgesetzte Anweisung.
"""

import pytest

from src.features.ai_assistant.repository import mindmaps as repo


class _FakeCursor:
    def __init__(self, rows, calls):
        self._rows = list(rows)
        self._calls = calls
        self.rowcount = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self._calls.append(("execute", " ".join(sql.split()), params))
        self.rowcount = 1

    def fetchone(self):
        return self._rows.pop(0) if self._rows else None

    def fetchall(self):
        return list(self._rows)


class _FakeConn:
    def __init__(self, rows, calls):
        self._rows = rows
        self._calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self, *a, **kw):
        return _FakeCursor(self._rows, self._calls)

    def commit(self):
        self._calls.append(("commit", None, None))


@pytest.fixture
def aufrufe(monkeypatch):
    calls = []
    rows = []

    def _fake_connection():
        return _FakeConn(rows, calls)

    monkeypatch.setattr(repo, "get_connection", _fake_connection)
    return calls, rows


def test_liste_bevorzugt_den_eigenen_titel(aufrufe):
    calls, rows = aufrufe
    rows.append({"id": 1, "status": "success", "created_at": None, "topic": "Von Hand benannt"})
    ergebnis = repo.get_all_aia_mindmaps(7, 3)
    sql = calls[0][1]
    assert "COALESCE(title, mindmap->>'topic')" in sql
    assert "AS topic" in sql
    assert ergebnis[0]["topic"] == "Von Hand benannt"


def test_update_schreibt_den_titel_nur_wenn_einer_kommt(aufrufe):
    calls, _ = aufrufe
    repo.update_aia_mindmap(1, "success", mindmap={"topic": "x"})
    assert "title" not in calls[0][1]

    calls.clear()
    repo.update_aia_mindmap(2, "success", mindmap={"topic": "x"}, title="Neuer Titel")
    assert "title = %s" in calls[0][1]
    assert "Neuer Titel" in calls[0][2]
