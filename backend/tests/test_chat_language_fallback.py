"""Sprach-Anker fuer den Chat: die letzte Frage der Person.

Warum es diese Abfrage gibt: der Chat schickt keinen Verlauf an das Modell,
jede Frage steht allein. Bei "hi" oder "klsdf" gibt es deshalb kein
Sprachsignal und die Antwort kippt ins Englische. Die letzte echte Frage aus
demselben Chat dient als Anker, damit die Sprache erhalten bleibt.

Alles offline. Die Datenbankverbindung wird durch eine Attrappe ersetzt, die
eine vorgegebene Zeile liefert und die abgesetzte Anweisung mitschreibt.
"""

import pytest

from src.features.ai_assistant.repository import chat as repo_chat


class _FakeCursor:
    def __init__(self, row, calls):
        self._row = row
        self._calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self._calls.append((sql, params))

    def fetchone(self):
        return self._row

    def fetchall(self):
        return self._row or []


class _FakeConn:
    def __init__(self, row, calls):
        self._row = row
        self._calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self, **kwargs):
        return _FakeCursor(self._row, self._calls)

    def commit(self):
        pass


@pytest.fixture
def fake_db(monkeypatch):
    """Haengt die Verbindung aus und gibt die Liste der Anweisungen zurueck."""
    def _apply(row):
        calls: list[tuple] = []
        monkeypatch.setattr(repo_chat, "get_connection", lambda: _FakeConn(row, calls))
        return calls
    return _apply


def test_letzte_fragen_neueste_zuerst(fake_db):
    fake_db([{"content": "klsdf"}, {"content": "Was bedeutet Quellenkritik?"}])
    assert repo_chat.get_last_aia_user_questions(1, 2) == [
        "klsdf", "Was bedeutet Quellenkritik?"]


def test_ohne_verlauf_gibt_es_keinen_anker(fake_db):
    fake_db([])
    assert repo_chat.get_last_aia_user_questions(1, 2) == []


def test_leere_eintraege_fallen_raus(fake_db):
    fake_db([{"content": "   "}, {"content": None}, {"content": "Hallo Welt"}])
    assert repo_chat.get_last_aia_user_questions(1, 2) == ["Hallo Welt"]


def test_nur_fragen_der_person_und_wenige_davon(fake_db):
    calls = fake_db([{"content": "egal"}])
    repo_chat.get_last_aia_user_questions(1, 2, limit=3)
    sql, params = calls[0]
    # Antworten des Tutors sind kein Anker, sonst wuerde dessen Sprachwahl
    # sich selbst verstaerken.
    assert "role = 'user'" in sql
    assert "ORDER BY created_at DESC" in sql
    assert "LIMIT %s" in sql
    assert params[:2] == (1, 2)
    assert params[-1] == 3


def test_es_werden_mehr_fragen_geholt_als_gebraucht(fake_db):
    # Kurze Eingaben ("hi", "ok") fallen spaeter als Sprachprobe raus, deshalb
    # muss der Verlauf tief genug gelesen werden, damit eine echte Frage
    # uebrig bleibt.
    calls = fake_db([{"content": "egal"}])
    repo_chat.get_last_aia_user_questions(1, 2)
    _, params = calls[0]
    assert params[-1] >= 10


def test_zugangslink_hat_seinen_eigenen_verlauf(fake_db):
    # Chats je Zugangslink sind getrennt, der Anker darf nicht aus einem
    # anderen Verlauf stammen.
    calls = fake_db([{"content": "egal"}])
    repo_chat.get_last_aia_user_questions(1, 2, enrollment_id=7, limit=3)
    sql, params = calls[0]
    assert "enrollment_id = %s" in sql
    assert params == (1, 2, 7, 3)

    calls = fake_db([{"content": "egal"}])
    repo_chat.get_last_aia_user_questions(1, 2, limit=3)
    sql, params = calls[0]
    assert "enrollment_id IS NULL" in sql
    assert params == (1, 2, 3)
