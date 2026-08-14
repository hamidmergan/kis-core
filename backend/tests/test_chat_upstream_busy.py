"""Der Chat sagt, wenn der Anbieter das Problem war.

Bisher bekam der Student fuer JEDEN Stromfehler denselben Satz, "Es ist ein
Fehler aufgetreten". Ein ueberlasteter Anbieter, ein falsch eingestelltes Modell
und ein echter Programmfehler sahen damit gleich aus, obwohl nur im ersten Fall
etwas zu tun ist, naemlich spaeter noch einmal fragen.

Die Aufraeumung der Aufraege kennt diese Unterscheidung schon (``is_upstream_busy``).
Sie liegt jetzt an einer neutralen Stelle, damit der Chat sie mitbenutzt, statt eine
zweite Markerliste zu pflegen, die irgendwann auseinanderlaeuft.
"""
import pytest

from src.services.upstream_errors import is_upstream_busy, upstream_error_code


@pytest.mark.parametrize("meldung", [
    "Error code: 502 - Bad Gateway",
    "Error code: 429 - Too Many Requests",
    "TTS API error (500): Internal Server Error",
    "Request timed out.",
    "Service Unavailable",
])
def test_anbieterprobleme_bekommen_den_schluessel(meldung):
    assert upstream_error_code(RuntimeError(meldung)) == "upstream_busy"


@pytest.mark.parametrize("meldung", [
    "Kein Embedding-Anbieter aktiv. Bitte im Admin-Bereich setzen.",
    "list index out of range",
    "Error code: 401 - Unauthorized",
])
def test_alles_andere_bekommt_keinen_schluessel(meldung):
    """Ohne diese Grenze wuerde ein Konfigurations- oder Programmfehler als
    'versuch es spaeter' verkauft, und niemand sucht die echte Ursache."""
    assert upstream_error_code(RuntimeError(meldung)) is None


def test_die_auftraege_benutzen_dieselbe_pruefung():
    """Der Umzug darf den Auftragsweg nicht abhaengen. Waeren es zwei Listen,
    wuerde ein neuer Fehlercode irgendwann nur an einer Stelle nachgetragen."""
    from src.tasks._errors import is_upstream_busy as auftrag_pruefung

    assert auftrag_pruefung is is_upstream_busy
