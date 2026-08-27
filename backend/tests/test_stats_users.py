"""The user numbers, checked where a number goes quietly wrong."""
from unittest.mock import MagicMock, patch

from src.features.stats import users as u


class FakeCursor:
    def __init__(self, rows):
        self._rows = rows

    def execute(self, sql, args=None):
        pass

    def fetchall(self):
        return self._rows


def test_ein_schluessel_ohne_nutzer_blaeht_die_zahl_nicht_auf():
    """Whoever can be resolved is counted."""
    cur = FakeCursor([{"id": 1, "display_name": "Hans", "ldap_username": "h"}])
    ergebnis = u._online_details(cur, {1: 1750000000, 4242: 1750000000})
    assert ergebnis["count"] == 1
    assert [x["name"] for x in ergebnis["users"]] == ["Hans"]


def test_niemand_online_gibt_null_und_leere_liste():
    assert u._online_details(FakeCursor([]), {}) == {"count": 0, "users": []}


def test_ohne_namen_steht_der_anmeldename():
    cur = FakeCursor([{"id": 2, "display_name": "", "ldap_username": "mmuster"}])
    assert u._online_details(cur, {2: 1750000000})["users"][0]["name"] == "mmuster"


def test_ohne_beides_steht_unbekannt():
    cur = FakeCursor([{"id": 3, "display_name": None, "ldap_username": None}])
    assert u._online_details(cur, {3: 1750000000})["users"][0]["name"] == "Unbekannt"


def test_die_schwelle_fuer_regelmaessig_steht_im_code():
    """An invented number in the chart would be worse than a named one."""
    assert u.REGELMAESSIG_AB_TAGEN == 10


def test_die_drei_gruppen_teilen_die_nutzer_ohne_ueberschneidung():
    cur = MagicMock()
    cur.fetchall.return_value = [
        {"tage": 1, "n": 5},    # genau einmal
        {"tage": 4, "n": 3},    # gelegentlich
        {"tage": 10, "n": 2},   # noch gelegentlich, Schwelle ist "mehr als"
        {"tage": 11, "n": 1},   # regelmaessig
    ]
    r = u._retention(cur)
    assert (r["once"], r["occasional"], r["regular"]) == (5, 5, 1)
    assert r["once"] + r["occasional"] + r["regular"] == 11


def test_wie_lange_jemand_schon_da_ist():
    """Measured from the first heartbeat, not from the last ping."""
    import time
    cur = FakeCursor([{"id": 1, "display_name": "Hans", "ldap_username": "h"}])
    vor_zehn_minuten = int(time.time()) - 600
    assert u._online_details(cur, {1: vor_zehn_minuten})["users"][0]["minutes"] == 10
