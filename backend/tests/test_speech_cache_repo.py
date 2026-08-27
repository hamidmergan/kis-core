"""The database side of the pronunciation cache, including row and file drifting apart."""

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
        # Untruncated, otherwise the tests would silently pass.
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
    """Without a commit the refresh rolls back and the cleanup throws away too much."""
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
    """Two concurrent stores must not fail."""
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
    """If the audio stayed in the row it would keep sitting in every backup."""
    calls = fake_db()

    repo.put("abc", b"ID3-ton")

    anweisung = _sql(calls)[0]
    assert "INSERT INTO aia_speech_cache (fingerprint, bytes)" in anweisung, \
        "die Zeile traegt nur noch die Nutzungsspur, der Ton gehoert in den Speicher"


def test_ablegen_schreibt_erst_die_datei_dann_die_zeile(fake_db, monkeypatch, lokal):
    """A row without a file looks like a hit and delivers nothing."""
    calls = fake_db()
    monkeypatch.setattr(storage, "save_speech_audio", _wirft)

    with pytest.raises(RuntimeError):
        repo.put("abc", b"ID3-ton")

    assert calls == [], "ohne Datei darf keine Zeile entstehen"


def test_leerer_ton_wird_nicht_abgelegt(fake_db, lokal):
    """An empty audio file in the cache would be worse than none."""
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
    """Without a row there is no file, a reach into the bucket would be wasted."""
    fake_db(rows=[])
    monkeypatch.setattr(storage, "get_speech_audio", _wirft)

    assert repo.get("gibtesnicht") is None


def test_zeile_ohne_datei_wird_weggeraeumt(fake_db, lokal):
    """Otherwise the sentence stays silent forever."""
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
    """Files first, then rows, otherwise nobody ever finds them again."""
    calls = fake_db(rows=[("abc",)])
    monkeypatch.setattr(storage, "delete_speech_audio", _wirft)

    with pytest.raises(RuntimeError):
        repo.prune(90)

    assert not [s for s in _sql(calls) if s.startswith("DELETE")], \
        "solange die Datei liegt, muss auch die Zeile liegen bleiben"


def test_aufraeumen_ohne_treffer_ruehrt_nichts_an(fake_db, lokal):
    """S3 rejects an empty delete list as an error."""
    calls = fake_db(rows=[])

    assert repo.prune(90) == 0

    assert not [s for s in _sql(calls) if s.startswith("DELETE")]


def _wirft(*args, **kwargs):
    raise RuntimeError("Speicher nicht erreichbar")
