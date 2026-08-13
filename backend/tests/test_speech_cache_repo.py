"""Die Datenbankseite des Aussprache-Vorrats.

Geschrieben aus demselben Grund wie ``test_exercise_pool_repo``: diese Schicht hat
beim Bauen schon einmal einen fehlenden ``commit`` durchgelassen. Die Verbindung aus
dem Pool committet nicht von selbst, und ein einzelner Aufruf sieht ohne Commit
richtig aus. Auffallen wuerde es erst beim zweiten, und genau so ist es passiert:
Ablegen und sofort Holen lieferte None.

Seit die Toene im Speicher liegen und nicht mehr in der Zeile, kommt die zweite
Sorte Fehler dazu: Zeile und Datei koennen auseinanderlaufen. Die Tests unten legen
fest, in welche Richtung das ausgehen darf, naemlich immer in die, aus der sich der
Vorrat von selbst erholt.

Die Datenbank ist hier gefaelscht, der Speicher nicht: er laeuft ueber die
``lokal``-Fixture gegen echte Dateien.
"""

import pytest

from src import storage
from src.features.ai_assistant.repository import speech_cache as repo


class _FakeCursor:
    def __init__(self, rows, calls):
        self._rows = rows
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

    def fetchall(self):
        alle, self._rows[:] = list(self._rows), []
        return alle


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
        zeilen = list(rows)
        monkeypatch.setattr(repo, "get_connection", lambda: _FakeConn(zeilen, calls))
        return calls
    return _apply


def _sql(calls):
    return [c[1] for c in calls if c[0] == "execute"]


def _params(calls):
    return [c[2] for c in calls if c[0] == "execute"]


# --- schreiben committen -----------------------------------------------------

def test_ablegen_committet(fake_db, lokal):
    calls = fake_db()
    repo.put("abc", b"ID3")
    assert ("commit", None, None) in calls, "ohne commit sieht der naechste Aufruf nichts"


def test_holen_committet_auch(fake_db, lokal):
    """Das Auffrischen des Zeitstempels ist ein Schreibvorgang. Ohne commit rollt die
    Verbindung ihn zurueck, und das naechtliche Aufraeumen wirft vielgehoerte Saetze weg."""
    calls = fake_db(rows=[("abc",)])
    storage.save_speech_audio("abc", b"ID3")
    repo.get("abc")
    assert ("commit", None, None) in calls


def test_aufraeumen_committet(fake_db, lokal):
    calls = fake_db(rows=[("abc",)])
    repo.prune(90)
    assert ("commit", None, None) in calls


# --- ablegen -----------------------------------------------------------------

def test_ablegen_kollidiert_nicht(fake_db, lokal):
    """Klicken zwei Lernende gleichzeitig denselben Satz, erzeugen beide und beide
    legen ab. Der zweite Schreibvorgang darf daran nicht scheitern."""
    calls = fake_db()
    repo.put("abc", b"ID3")
    anweisung = _sql(calls)[0]
    assert "ON CONFLICT (fingerprint) DO UPDATE" in anweisung
    assert "last_used_at = NOW()" in anweisung


def test_ablegen_traegt_die_groesse_ein(fake_db, lokal):
    calls = fake_db()
    repo.put("abc", b"1234567890")
    params = _params(calls)[0]
    assert params[0] == "abc"
    assert params[1] == 10


def test_ablegen_legt_den_ton_in_den_speicher(fake_db, lokal):
    calls = fake_db()

    repo.put("abc", b"ID3-ton")

    assert storage.get_speech_audio("abc") == b"ID3-ton"
    assert calls, "die Zeile muss trotzdem geschrieben werden, sie traegt die Nutzungsspur"


def test_ablegen_schickt_keine_bytes_mehr_an_die_datenbank(fake_db, lokal):
    """Der eigentliche Zweck des Umbaus. Bliebe der Ton zusaetzlich in der Zeile, waere
    nichts gewonnen: er steckte weiter in jeder Sicherung."""
    calls = fake_db()

    repo.put("abc", b"ID3-ton")

    anweisung = _sql(calls)[0]
    assert "INSERT INTO aia_speech_cache (fingerprint, bytes)" in anweisung, \
        "die Zeile traegt nur noch die Nutzungsspur, der Ton gehoert in den Speicher"


def test_ablegen_schreibt_erst_die_datei_dann_die_zeile(fake_db, monkeypatch, lokal):
    """Eine Zeile ohne Datei sieht wie ein Treffer aus und liefert nichts. Andersherum
    liegt eine Datei ohne Zeile herum, die der naechste Versuch einfach ueberschreibt."""
    calls = fake_db()
    monkeypatch.setattr(storage, "save_speech_audio", _wirft)

    with pytest.raises(RuntimeError):
        repo.put("abc", b"ID3-ton")

    assert calls == [], "ohne Datei darf keine Zeile entstehen"


def test_leerer_ton_wird_nicht_abgelegt(fake_db, lokal):
    """Ein leerer Ton im Vorrat waere schlimmer als keiner: er sieht wie ein Treffer
    aus und spielt nichts."""
    calls = fake_db()
    repo.put("abc", b"")
    assert calls == []
    assert storage.get_speech_audio("abc") is None


# --- holen -------------------------------------------------------------------

def test_holen_frischt_den_zeitstempel_auf(fake_db, lokal):
    calls = fake_db(rows=[("abc",)])
    storage.save_speech_audio("abc", b"ID3")

    repo.get("abc")

    anweisung = _sql(calls)[0]
    assert anweisung.startswith("UPDATE aia_speech_cache SET last_used_at = NOW()")
    assert "RETURNING fingerprint" in anweisung


def test_holen_liefert_den_ton_aus_dem_speicher(fake_db, lokal):
    fake_db(rows=[("abc",)])
    storage.save_speech_audio("abc", b"ID3-ton")

    ergebnis = repo.get("abc")

    assert ergebnis == b"ID3-ton"
    assert isinstance(ergebnis, bytes)


def test_unbekannter_schluessel_liefert_nichts(fake_db, lokal):
    fake_db(rows=[])
    assert repo.get("gibtesnicht") is None


def test_unbekannter_schluessel_fragt_den_speicher_nicht(fake_db, monkeypatch, lokal):
    """Ohne Zeile gibt es auch keine Datei. Ein Griff in den Bucket waere ein
    Netzweg fuer eine Antwort, die schon feststeht."""
    fake_db(rows=[])
    monkeypatch.setattr(storage, "get_speech_audio", _wirft)

    assert repo.get("gibtesnicht") is None


def test_zeile_ohne_datei_wird_weggeraeumt(fake_db, lokal):
    """Sonst bleibt der Satz fuer immer stumm: die Zeile meldet einen Treffer, die
    Datei fehlt, und niemand spricht ihn je wieder."""
    calls = fake_db(rows=[("abc",)])

    assert repo.get("abc") is None

    aufraeumen = [s for s in _sql(calls) if s.startswith("DELETE")]
    assert aufraeumen, "die Zeile muss weg, sonst heilt sich das nie"
    assert "WHERE fingerprint = %s" in aufraeumen[0]


# --- aufraeumen --------------------------------------------------------------

def test_aufraeumen_sucht_nach_dem_letzten_abruf(fake_db, lokal):
    calls = fake_db(rows=[("abc",)])

    geloescht = repo.prune(30)

    anweisung, params = [(c[1], c[2]) for c in calls if c[0] == "execute"][0]
    assert "FROM aia_speech_cache" in anweisung
    assert "last_used_at <" in anweisung
    assert params == ("30 days",)
    assert geloescht == 1


def test_aufraeumen_nimmt_ohne_angabe_die_hausnummer(fake_db, lokal):
    calls = fake_db(rows=[("abc",)])
    repo.prune()
    assert _params(calls)[0] == (f"{repo.SPEECH_CACHE_RETENTION_DAYS} days",)


def test_aufraeumen_loescht_auch_die_toene(fake_db, lokal):
    fake_db(rows=[("abc",), ("def",)])
    storage.save_speech_audio("abc", b"alt")
    storage.save_speech_audio("def", b"auch alt")
    storage.save_speech_audio("ghi", b"frisch")

    repo.prune(90)

    assert storage.get_speech_audio("abc") is None
    assert storage.get_speech_audio("def") is None
    assert storage.get_speech_audio("ghi") == b"frisch"


def test_aufraeumen_loescht_die_toene_vor_den_zeilen(fake_db, monkeypatch, lokal):
    """Die Reihenfolge ist der Unterschied zwischen einem Ton, der beim naechsten Lauf
    noch einmal drankommt, und einem, den nie wieder jemand findet: ohne seine Zeile
    weiss niemand mehr, dass es ihn gibt."""
    calls = fake_db(rows=[("abc",)])
    monkeypatch.setattr(storage, "delete_speech_audio", _wirft)

    with pytest.raises(RuntimeError):
        repo.prune(90)

    assert not [s for s in _sql(calls) if s.startswith("DELETE")], \
        "solange die Datei liegt, muss auch die Zeile liegen bleiben"


def test_aufraeumen_ohne_treffer_ruehrt_nichts_an(fake_db, lokal):
    """Der Normalfall jeder Nacht. Ein DELETE ueber die ganze Tabelle waere hier
    reine Last, und ``delete_objects`` mit leerer Liste weist S3 als Fehler ab."""
    calls = fake_db(rows=[])

    assert repo.prune(90) == 0

    assert not [s for s in _sql(calls) if s.startswith("DELETE")]


def _wirft(*args, **kwargs):
    raise RuntimeError("Speicher nicht erreichbar")
