"""Die Datenbankseite des Aussprache-Vorrats.

Geschrieben aus demselben Grund wie ``test_exercise_pool_repo``: diese Schicht hat
beim Bauen schon einmal einen fehlenden ``commit`` durchgelassen. Die Verbindung aus
dem Pool committet nicht von selbst, und ein einzelner Aufruf sieht ohne Commit
richtig aus. Auffallen wuerde es erst beim zweiten, und genau so ist es passiert:
Ablegen und sofort Holen lieferte None.

Die Fachtests in ``test_flashcard_speech`` ersetzen diese Schicht durch ein
Woerterbuch, sie koennen den Fehler also nie sehen. Hier wird die tatsaechliche
Anweisung geprueft.
"""

import pytest

from src.features.ai_assistant.repository import speech_cache as repo


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
        # Ungekuerzt: die Tests unten pruefen Bestandteile der Anweisung, ein
        # Abschneiden wuerde sie stillschweigend gruen machen.
        self._calls.append(("execute", " ".join(sql.split()), params))
        self.rowcount = 7

    def fetchone(self):
        return self._rows.pop(0) if self._rows else None


class _FakeConn:
    def __init__(self, rows, calls):
        self._rows = rows
        self._calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self, **kwargs):
        return _FakeCursor(self._rows, self._calls)

    def commit(self):
        self._calls.append(("commit", None, None))


@pytest.fixture
def fake_db(monkeypatch):
    def _apply(rows=()):
        calls: list[tuple] = []
        monkeypatch.setattr(repo, "get_connection", lambda: _FakeConn(rows, calls))
        return calls
    return _apply


def _sql(calls):
    return [c[1] for c in calls if c[0] == "execute"]


# --- schreiben committen -----------------------------------------------------

def test_ablegen_committet(fake_db):
    calls = fake_db()
    repo.put("abc", b"ID3")
    assert ("commit", None, None) in calls, "ohne commit sieht der naechste Aufruf nichts"


def test_holen_committet_auch(fake_db):
    """Das Auffrischen des Zeitstempels ist ein Schreibvorgang. Ohne commit rollt die
    Verbindung ihn zurueck, und das naechtliche Aufraeumen wirft vielgehoerte Saetze weg."""
    calls = fake_db(rows=[(b"ID3",)])
    repo.get("abc")
    assert ("commit", None, None) in calls


def test_aufraeumen_committet(fake_db):
    calls = fake_db()
    repo.prune(90)
    assert ("commit", None, None) in calls


# --- die Anweisungen selbst --------------------------------------------------

def test_ablegen_kollidiert_nicht(fake_db):
    """Klicken zwei Lernende gleichzeitig denselben Satz, erzeugen beide und beide
    legen ab. Der zweite Schreibvorgang darf daran nicht scheitern."""
    calls = fake_db()
    repo.put("abc", b"ID3")
    anweisung = _sql(calls)[0]
    assert "ON CONFLICT (fingerprint) DO UPDATE" in anweisung
    assert "last_used_at = NOW()" in anweisung


def test_ablegen_traegt_die_groesse_ein(fake_db):
    calls = fake_db()
    repo.put("abc", b"1234567890")
    params = [c[2] for c in calls if c[0] == "execute"][0]
    assert params[0] == "abc"
    assert params[2] == 10


def test_holen_frischt_den_zeitstempel_auf(fake_db):
    calls = fake_db(rows=[(b"ID3",)])
    repo.get("abc")
    anweisung = _sql(calls)[0]
    assert anweisung.startswith("UPDATE aia_speech_cache SET last_used_at = NOW()")
    assert "RETURNING audio" in anweisung


def test_holen_liefert_echte_bytes(fake_db):
    """psycopg2 gibt BYTEA als memoryview zurueck. Wer das durchreicht, bekommt an
    anderer Stelle Aerger, etwa beim Laengenvergleich oder in der Antwort."""
    fake_db(rows=[(memoryview(b"ID3-audio"),)])
    ergebnis = repo.get("abc")
    assert ergebnis == b"ID3-audio"
    assert isinstance(ergebnis, bytes)


def test_unbekannter_schluessel_liefert_nichts(fake_db):
    fake_db(rows=[])
    assert repo.get("gibtesnicht") is None


def test_leerer_ton_wird_nicht_abgelegt(fake_db):
    """Ein leerer Ton im Vorrat waere schlimmer als keiner: er sieht wie ein Treffer
    aus und spielt nichts."""
    calls = fake_db()
    repo.put("abc", b"")
    assert calls == []


def test_aufraeumen_nimmt_die_tage_entgegen(fake_db):
    calls = fake_db()
    geloescht = repo.prune(30)
    anweisung, params = [(c[1], c[2]) for c in calls if c[0] == "execute"][0]
    assert "DELETE FROM aia_speech_cache" in anweisung
    assert "last_used_at <" in anweisung
    assert params == ("30 days",)
    assert geloescht == 7


def test_aufraeumen_nimmt_ohne_angabe_die_hausnummer(fake_db):
    calls = fake_db()
    repo.prune()
    params = [c[2] for c in calls if c[0] == "execute"][0]
    assert params == (f"{repo.SPEECH_CACHE_RETENTION_DAYS} days",)
