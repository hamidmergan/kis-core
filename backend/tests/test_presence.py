"""Anwesenheit: wer gerade da ist, und an welchen Stunden jemand da war.

Warum es das braucht: angemeldet ist nicht online. Der Sitzungsschluessel laeuft
24 Stunden ab der Anmeldung, nicht ab der letzten Handlung. Wer sich morgens
anmeldet und den Laptop zuklappt, gaelte sonst den ganzen Tag als anwesend.

Die Tests hier pruefen vor allem eins: ein Fehler beim Mitschreiben darf nie
den Stream reissen, an dem ein Nutzer gerade haengt.
"""
from unittest.mock import MagicMock, patch

from src.security import presence


def test_ein_lebenszeichen_setzt_einen_schluessel_mit_frist():
    r = MagicMock()
    with patch.object(presence, "_redis", return_value=r):
        presence.touch(7)
    r.set.assert_called_once()
    assert r.set.call_args.kwargs["ex"] == presence.TTL_SECONDS


def test_die_frist_ist_laenger_als_der_ping_abstand():
    """Der Stream pingt alle zwanzig Sekunden. Waere die Frist kuerzer, gaelte
    jeder als weg, sobald die Leitung einmal stockt."""
    assert presence.TTL_SECONDS > 20


def test_ohne_gueltige_nutzernummer_passiert_nichts():
    r = MagicMock()
    with patch.object(presence, "_redis", return_value=r):
        presence.touch(0)
        presence.touch(-1)
    r.set.assert_not_called()


def test_ein_redis_ausfall_reisst_den_stream_nicht():
    with patch.object(presence, "_redis", side_effect=RuntimeError("Redis weg")):
        presence.touch(7)  # darf nicht werfen


def test_ohne_redis_ist_niemand_online_statt_geraten():
    """Eine Statistik, die kurz nichts anzeigt, ist besser als eine, die raet."""
    with patch.object(presence, "_redis", side_effect=RuntimeError("Redis weg")):
        assert presence.online_user_ids() == []


def test_die_online_liste_kommt_aus_den_schluesseln():
    r = MagicMock()
    r.keys.return_value = [b"kis:seen:9", b"kis:seen:3"]
    r.mget.return_value = [b"1750000000", b"1750000000"]
    with patch.object(presence, "_redis", return_value=r):
        assert presence.online_user_ids() == [3, 9]


def test_eine_kaputte_datenbank_reisst_den_stream_nicht():
    with patch.object(presence, "get_connection", side_effect=RuntimeError("DB weg")):
        presence.mark_hour(7)  # darf nicht werfen


def test_ohne_gueltige_nutzernummer_keine_stunde():
    with patch.object(presence, "get_connection") as verbindung:
        presence.mark_hour(0)
    verbindung.assert_not_called()


def test_ein_alter_schluessel_ergibt_keine_millionen_minuten():
    """Fruehere Fassungen schrieben eine schlichte "1" in den Schluessel.
    Ohne Abfangen wuerden daraus 29 Millionen Minuten Anwesenheit."""
    r = MagicMock()
    r.keys.return_value = [b"kis:seen:7"]
    r.mget.return_value = [b"1"]
    with patch.object(presence, "_redis", return_value=r):
        seit = presence.online_since()
    import time as _t
    assert abs(seit[7] - int(_t.time())) < 5


def test_ein_gueltiger_zeitpunkt_bleibt_stehen():
    r = MagicMock()
    r.keys.return_value = [b"kis:seen:7"]
    r.mget.return_value = [b"1750000000"]
    with patch.object(presence, "_redis", return_value=r):
        assert presence.online_since()[7] == 1750000000


def test_das_lebenszeichen_ueberschreibt_den_anfang_nicht():
    """Sonst waere jeder immer "seit 0 Minuten" da."""
    r = MagicMock()
    with patch.object(presence, "_redis", return_value=r):
        presence.touch(7)
    assert r.set.call_args.kwargs["nx"] is True
    r.expire.assert_called_once()
