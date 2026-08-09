"""Ein Grammatikthema entfernen, ohne fertige Aufgabensaetze auszuhoehlen.

Eine Aufgabe aus dem Vorrat wird beim Bauen eines Satzes nicht kopiert, der Satz
zeigt nur dorthin (``pool_item_id``). Der Vorrat haengt am Thema und geht mit ihm
weg. Ohne Vorkehrung stuende danach jemand vor einem Satz ohne Loesung und ohne
Erklaerung, nur weil eine Lehrkraft ein Thema aufgeraeumt hat.

Denselben Schutz gibt es beim Loeschen einer Quelle schon, siehe
``clear_pool_for_source``. Diese Tests halten fest, dass das Thema ihn auch hat.
"""

import pytest

from src.features.ai_assistant.repository import exercise_pool as vorrat
from src.features.ai_assistant.repository import grammar_topics as themen


class _FakeCursor:
    def __init__(self, calls):
        self._calls = calls
        self.rowcount = 2

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self._calls.append((" ".join(sql.split()), params))

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
        self._calls.append(("COMMIT", None))


@pytest.fixture
def calls(monkeypatch):
    """Alle Anweisungen beider Ablagen in einer Liste, in der Reihenfolge des Laufs."""
    protokoll: list[tuple] = []
    for modul in (vorrat, themen):
        monkeypatch.setattr(modul, "get_connection", lambda: _FakeConn(protokoll))
    return protokoll


def _anweisungen(calls):
    return [sql for sql, _ in calls]


def test_der_inhalt_wird_zurueckgeschrieben_bevor_das_thema_faellt(calls):
    themen.delete_grammar_topic(7)
    sql = _anweisungen(calls)
    zurueck = next(i for i, a in enumerate(sql) if a.startswith("UPDATE aia_exercise_items"))
    weg = next(i for i, a in enumerate(sql) if "DELETE FROM aia_grammar_topics" in a)
    assert zurueck < weg, "erst retten, dann loeschen, sonst ist der Inhalt fort"


def test_zurueckgeschrieben_wird_nur_der_vorrat_dieses_themas(calls):
    themen.delete_grammar_topic(7)
    update = next(p for sql, p in calls if sql.startswith("UPDATE aia_exercise_items"))
    assert update == (7,)


def test_das_zurueckschreiben_wird_committet(calls):
    # Ohne Commit sieht das DELETE der naechsten Verbindung die Rettung nicht.
    vorrat.materialize_pool_items_for_topic(7)
    assert ("COMMIT", None) in calls


def test_die_quelle_bleibt_ihr_eigener_weg(calls):
    # Beide Wege schreiben dasselbe zurueck, nur nach anderem Merkmal gefiltert.
    vorrat.materialize_pool_items(9)
    sql, params = next(c for c in calls if c[0].startswith("UPDATE aia_exercise_items"))
    assert "p.source_id = %s" in sql and params == (9,)
