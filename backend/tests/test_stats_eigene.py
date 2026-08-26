"""Die Statistik, die nur die eigenen Module zeigt.

Der Bereich Statistik war bisher ganz oder gar nicht: wer hineindurfte, sah
jedes Modul jedes Kollegen. Eine Lehrperson braucht aber genau die drei Module,
die sie betreut, und die Leute darin.

Der Schwerpunkt liegt deshalb auf der Grenze. Eine Zahl, die zu viel zeigt,
faellt niemandem auf, sie sieht nur nach mehr Betrieb aus.
"""

import pytest
from fastapi import HTTPException

from src.features.stats import eigene
from src.permissions_registry import (
    ALL_PERMISSION_KEYS,
    PERM_SET_AIA_USAGE,
    PERM_SET_STATS_MODELS,
    PERM_SET_STATS_OWN,
    PERM_SET_STATS_USERS,
    PERM_SET_TOOLS_STATS,
    PERMISSION_GROUPS,
    is_settings_key,
)
from src.routes.admin import stats as stats_route

EIGNER = 7
TUTOR = 8
LERNENDE = 9
FREMD = 99


# ── Der Schluessel ───────────────────────────────────────────────────────────

def test_der_neue_schluessel_steht_im_katalog():
    assert PERM_SET_STATS_OWN in ALL_PERMISSION_KEYS


def test_die_beiden_modul_rechte_stehen_direkt_untereinander():
    """Beide Zeilen handeln von Modulen, die eine eingeschraenkt, die andere
    nicht. Standen zwei fremde Zeilen dazwischen, las man sie als zwei Themen
    statt als Paar und hakte im Zweifel beide an.
    """
    assert PERMISSION_GROUPS["set.statistik"] == (
        PERM_SET_STATS_OWN,
        PERM_SET_AIA_USAGE,
        PERM_SET_STATS_USERS,
        PERM_SET_TOOLS_STATS,
        PERM_SET_STATS_MODELS,
    )


def test_er_ist_ein_einstellungsrecht_und_oeffnet_damit_den_bereich():
    """``allow_admin_panel`` heisst "hat irgendein settings.*". Ohne das
    Praefix bekaeme die Lehrperson das Recht, aber keine Tuer dazu."""
    assert is_settings_key(PERM_SET_STATS_OWN)


# ── Die Besitzpruefung ───────────────────────────────────────────────────────

@pytest.fixture
def modul(monkeypatch):
    """Ein Modul mit Eigentuemer, Tutor und einer Lernenden."""
    def _apply(vorhanden=True):
        monkeypatch.setattr(
            eigene.db, "get_aia_workspace",
            lambda uuid: {"id": 1, "uuid": uuid, "user_id": EIGNER} if vorhanden else None,
        )
        monkeypatch.setattr(
            eigene.db, "is_workspace_tutor",
            lambda workspace_id, user_id: user_id == TUTOR,
        )
    return _apply


def test_der_eigentuemer_darf(modul):
    modul()
    assert eigene.may_see_workspace("abc", EIGNER) is True


def test_der_tutor_darf_auch(modul):
    """Wie ueberall sonst: wer das Modul betreut, sieht auch seine Zahlen."""
    modul()
    assert eigene.may_see_workspace("abc", TUTOR) is True


def test_eine_eingeschriebene_lernende_darf_nicht(modul):
    """Der Kern der Sache. Wer im Modul lernt, sieht die Zahlen der anderen nie."""
    modul()
    assert eigene.may_see_workspace("abc", LERNENDE) is False


def test_ein_voellig_fremder_darf_nicht(modul):
    modul()
    assert eigene.may_see_workspace("abc", FREMD) is False


def test_ein_unbekanntes_modul_ist_kein_zugriff(modul):
    modul(vorhanden=False)
    assert eigene.may_see_workspace("weg", EIGNER) is False


# ── Die Liste der eigenen Module ─────────────────────────────────────────────

class _FakeCursor:
    def __init__(self, rows, calls):
        self._rows = list(rows)
        self._calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self._calls.append((" ".join(sql.split()), params))

    def fetchall(self):
        return list(self._rows)


class _FakeConn:
    def __init__(self, rows, calls):
        self._rows, self._calls = rows, calls

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self, **kwargs):
        return _FakeCursor(self._rows, self._calls)


@pytest.fixture
def fake_db(monkeypatch):
    def _apply(rows=()):
        calls: list[tuple] = []
        monkeypatch.setattr(eigene, "get_connection", lambda: _FakeConn(rows, calls))
        return calls
    return _apply


ZEILE = {
    "uuid": "u-1", "title": "Werkstoffkunde 2", "is_active": True, "access": "owner",
    "members": 41, "sources": 12, "chat": 684, "answered": 2140, "last": None,
}


def test_die_liste_nennt_die_eigene_rolle_je_modul(fake_db):
    fake_db([dict(ZEILE), dict(ZEILE, uuid="u-2", access="tutor")])

    module = eigene.own_workspaces(EIGNER)["workspaces"]

    assert [m["access"] for m in module] == ["owner", "tutor"]


def test_die_kacheln_summieren_ueber_die_eigenen_module(fake_db):
    fake_db([dict(ZEILE), dict(ZEILE, uuid="u-2", members=28, chat=421, answered=1508)])

    summe = eigene.own_workspaces(EIGNER)["totals"]

    assert summe == {"workspaces": 2, "members": 69, "chat": 1105, "answered": 3648}


def test_ohne_eigenes_modul_bleibt_die_seite_leer_statt_zu_werfen(fake_db):
    fake_db([])

    daten = eigene.own_workspaces(FREMD)

    assert daten["workspaces"] == []
    assert daten["totals"]["workspaces"] == 0


def test_die_liste_zaehlt_den_eigentuemer_mit_wie_die_detailansicht(fake_db):
    """Sonst steht in der Zeile 2 und im geoeffneten Modul 3, und man sucht den
    Fehler bei sich."""
    calls = fake_db([])

    eigene.own_workspaces(EIGNER)

    sql = calls[0][0]
    assert "e.user_id <> w.user_id" in sql, "der Eigentuemer darf nicht doppelt zaehlen"
    assert ") + 1 AS members" in sql, "und er muss ueberhaupt mitzaehlen"


def test_die_abfrage_laesst_nur_eigentum_und_tutor_durch(fake_db):
    """Ohne die Tutor-Bedingung waere die Liste eine Liste aller Module."""
    calls = fake_db([])

    eigene.own_workspaces(EIGNER)

    sql, params = calls[0]
    assert "w.user_id = %s" in sql
    assert "aia_enrollments" in sql and "role = 'tutor'" in sql
    assert set(params) == {EIGNER}, "die Nummer kommt aus der Anmeldung, sonst nichts"


# ── Die Routen ───────────────────────────────────────────────────────────────

async def test_die_liste_fragt_nach_dem_angemeldeten_nutzer(monkeypatch):
    """Der Filter darf nie aus der Adresse kommen, sonst ist er kein Filter."""
    gefragt = []
    monkeypatch.setattr(stats_route, "own_workspaces", lambda uid: gefragt.append(uid))

    await stats_route.get_own_stats(user={"user_id": EIGNER})

    assert gefragt == [EIGNER]


async def test_ein_fremdes_modul_antwortet_mit_404(monkeypatch):
    """404 und nicht 403: sonst verraet die Antwort, dass es das Modul gibt."""
    monkeypatch.setattr(stats_route, "may_see_workspace", lambda uuid, uid: False)

    with pytest.raises(HTTPException) as fehler:
        await stats_route.get_own_workspace_detail("fremd", user={"user_id": FREMD})

    assert fehler.value.status_code == 404


async def test_das_eigene_modul_kommt_durch(monkeypatch):
    monkeypatch.setattr(stats_route, "may_see_workspace", lambda uuid, uid: True)
    monkeypatch.setattr(stats_route, "workspace_detail", lambda uuid: {"uuid": uuid})

    daten = await stats_route.get_own_workspace_detail("meins", user={"user_id": EIGNER})

    assert daten == {"uuid": "meins"}


async def test_ein_geloeschtes_modul_antwortet_auch_mit_404(monkeypatch):
    """Die Pruefung sagt ja, die Detailabfrage findet nichts mehr."""
    monkeypatch.setattr(stats_route, "may_see_workspace", lambda uuid, uid: True)
    monkeypatch.setattr(stats_route, "workspace_detail", lambda uuid: None)

    with pytest.raises(HTTPException) as fehler:
        await stats_route.get_own_workspace_detail("weg", user={"user_id": EIGNER})

    assert fehler.value.status_code == 404
