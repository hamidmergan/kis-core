"""Ein Konto loeschen muss alles mitnehmen, was daran haengt.

Der teuerste Fehler waere eine vergessene Tabelle: die Zeilen bleiben mit einer
Nutzernummer stehen, die niemandem mehr gehoert, und tauchen spaeter in Zahlen
und Listen wieder auf. Deshalb prueft der erste Test das Schema selbst und
nicht nur den Ablauf.
"""
import re
from pathlib import Path

import pytest

from src.features.admin.repository import user_delete as ud

SCHEMA = Path(__file__).resolve().parents[1] / "src/core/db/schema.py"


class FakeCursor:
    """Merkt sich die abgesetzten Anweisungen und liefert feste Zeilen."""

    def __init__(self, protokoll, zeile=None):
        self._protokoll = protokoll
        self._zeile = zeile

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def execute(self, sql, args=None):
        self._protokoll.append((" ".join(sql.split()), args))

    def fetchone(self):
        return self._zeile


class FakeConnection:
    def __init__(self, protokoll, zeile=None):
        self._protokoll = protokoll
        self._zeile = zeile
        self.commits = 0

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def cursor(self, **kwargs):
        return FakeCursor(self._protokoll, self._zeile)

    def commit(self):
        self.commits += 1


@pytest.fixture
def protokoll(monkeypatch):
    """Klinkt die Datenbank aus und gibt die Liste der Anweisungen zurueck."""
    eintraege: list[tuple[str, object]] = []
    monkeypatch.setattr(ud, "get_connection", lambda: FakeConnection(eintraege))
    return eintraege


def _tabellen_mit_nutzerspalte() -> set[str]:
    """Alle Tabellen des Schemas, die eine Nutzernummer fuehren."""
    quelle = SCHEMA.read_text()
    treffer = re.findall(
        r"CREATE TABLE IF NOT EXISTS\s+(\w+)\s*\((.*?)\n\s*\)\s*\"\"\"", quelle, re.S
    )
    return {
        name for name, rumpf in treffer
        if re.search(r"\buser_id\b|\bcreated_by\b", rumpf)
    }


def test_jede_tabelle_mit_einer_nutzernummer_ist_bedacht():
    """Neue Tabelle mit user_id? Dann muss hier eine Entscheidung fallen."""
    gefunden = _tabellen_mit_nutzerspalte()
    assert len(gefunden) > 20, "Schema nicht gelesen, der Test wuerde blind bestehen"
    bedacht = set(ud.SWEEP_BY_USER_ID) | set(ud.SONDERFALL)
    assert gefunden - bedacht == set()


def test_keine_tabelle_steht_doppelt_in_den_listen():
    assert set(ud.SWEEP_BY_USER_ID) & set(ud.SONDERFALL) == set()


def test_alle_tabellen_der_liste_werden_wirklich_abgeraeumt(protokoll):
    ud.delete_user_completely(42)
    abgeraeumt = {
        m.group(1)
        for sql, _ in protokoll
        if (m := re.match(r"DELETE FROM (\w+) WHERE user_id", sql))
    }
    assert set(ud.SWEEP_BY_USER_ID) - abgeraeumt == set()


def test_die_arbeitsbereiche_gehen_vor_dem_konto(protokoll):
    """Erst die Kaskade ausloesen, dann die Zeile, an der sie haengt."""
    ud.delete_user_completely(42)
    reihenfolge = [sql for sql, _ in protokoll]
    arbeitsbereiche = next(i for i, s in enumerate(reihenfolge) if "aia_workspaces" in s)
    konto = next(i for i, s in enumerate(reihenfolge) if s.startswith("DELETE FROM users "))
    assert arbeitsbereiche < konto


def test_das_konto_geht_zuletzt(protokoll):
    ud.delete_user_completely(42)
    assert protokoll[-1][0].startswith("DELETE FROM users ")


def test_der_whitelist_eintrag_geht_mit(protokoll):
    """Sonst legt der naechste Login das Konto sofort wieder an."""
    ud.delete_user_completely(42)
    assert any("DELETE FROM whitelist" in sql for sql, _ in protokoll)


def test_die_leere_mailadresse_raeumt_die_whitelist_nicht_leer(protokoll):
    ud.delete_user_completely(42)
    whitelist = next(sql for sql, _ in protokoll if "DELETE FROM whitelist" in sql)
    assert "email <> ''" in whitelist


def test_grammatik_themen_verlieren_nur_den_urheber(protokoll):
    """Das Thema gehoert einem fremden Arbeitsbereich und bleibt dort stehen."""
    ud.delete_user_completely(42)
    themen = [sql for sql, _ in protokoll if "aia_grammar_topics" in sql]
    assert themen == ["UPDATE aia_grammar_topics SET created_by = NULL WHERE created_by = %s"]


def test_jede_anweisung_bekommt_die_nutzernummer(protokoll):
    ud.delete_user_completely(42)
    assert all(args == (42,) for _, args in protokoll)


def test_es_wird_genau_einmal_bestaetigt(monkeypatch):
    """Eine Transaktion, sonst bleibt ein halb geloeschtes Konto zurueck."""
    verbindung = FakeConnection([])
    monkeypatch.setattr(ud, "get_connection", lambda: verbindung)
    ud.delete_user_completely(42)
    assert verbindung.commits == 1


def test_die_vorschau_nennt_die_zahlen_fuer_die_rueckfrage(monkeypatch):
    zeile = {"workspaces": 3, "sources": 12, "messages": 240, "jobs": 5, "enrollments": 2}
    monkeypatch.setattr(ud, "get_connection", lambda: FakeConnection([], zeile))
    assert ud.count_user_footprint(42) == zeile


# --- Dateien -----------------------------------------------------------------

def _dateien_anlegen(wurzel, user_id: int) -> None:
    """Ein Arbeitsbereich und eine Aufgabe, so wie die Ablage sie anlegt."""
    ws = wurzel / f"users/{user_id}/aia/workspaces/w1/sources"
    ws.mkdir(parents=True, exist_ok=True)
    (ws / "quelle.pdf").write_bytes(b"pdf")
    job = wurzel / f"users/{user_id}/jobs/j1"
    job.mkdir(parents=True, exist_ok=True)
    (job / "ergebnis.txt").write_bytes(b"text")


def test_die_dateien_des_nutzers_verschwinden_mit_dem_konto(lokal):
    from src import storage

    _dateien_anlegen(lokal, 42)

    storage.delete_user_folder(42)

    assert not (lokal / "users/42").exists()


def test_eine_aehnliche_nutzernummer_bleibt_unberuehrt(lokal):
    """Ohne den Schraegstrich am Ende wuerde 4 auch 42 mitnehmen."""
    from src import storage

    _dateien_anlegen(lokal, 4)
    _dateien_anlegen(lokal, 42)

    storage.delete_user_folder(4)

    assert not (lokal / "users/4").exists()
    assert (lokal / "users/42/jobs/j1/ergebnis.txt").exists()


def test_geloescht_wird_gezaehlt(lokal):
    from src import storage

    _dateien_anlegen(lokal, 42)

    assert storage.delete_user_folder(42) == 2


def test_die_einladung_bleibt_und_verliert_nur_den_urheber(protokoll):
    """Die Einladung gehoert der eingeladenen Person, nicht der, die sie erzeugt hat."""
    ud.delete_user_completely(42)
    assert any(
        "UPDATE invites SET created_by = NULL" in sql for sql, _ in protokoll
    )
    assert not any("DELETE FROM invites" in sql for sql, _ in protokoll)
