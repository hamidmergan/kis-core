"""Erkennt, ob hinter einem Fehler der KI-Anbieter steckt und nicht die Eingabe.

Die Unterscheidung ist die zwischen "spaeter noch einmal versuchen" und "hier ist
wirklich etwas kaputt". Sie entstand fuer die Auftraege (Werkzeuge, Screencast) und
lag darum in ``src/tasks/_errors.py``. Der Chat braucht genau dieselbe Antwort, darf
aber nicht in ein privates Modul des Auftrags-Pakets greifen. Deshalb steht die
Pruefung hier neutral, und ``_errors.py`` importiert sie nur noch.

Bewusst EINE Markerliste fuer beide Wege: zwei Listen laufen auseinander, sobald
jemand einen neuen Fehlercode nur an der Stelle nachtraegt, die er gerade vor sich hat.
"""

from __future__ import annotations

# Meldungen, hinter denen der Dienst des Anbieters steckt und nicht die Eingabe
# der Nutzerin. Roh sahen die im Bildschirm so aus:
#   TTS API error (500): Internal Server Error
# Damit kann niemand etwas anfangen, und zu tun ist ohnehin nur eines, spaeter
# noch einmal versuchen. 500 gehoert ausdruecklich dazu, myLab beendet damit
# jede Anfrage, die ihm zu lange dauert.
_BUSY_MARKERS = (
    "429", "rate limit", "too many requests",
    "500", "internal server error",
    "502", "503", "504",
    "bad gateway", "service unavailable", "gateway timeout",
    "timeout", "timed out",
)

# Schluessel, den die Oberflaeche in ihren eigenen Text uebersetzt. Absichtlich ein
# Schluessel und kein fertiger Satz: die Chat-Texte liegen alle im Frontend, und ein
# vom Backend geschickter Satz waere die einzige Ausnahme davon.
UPSTREAM_BUSY = "upstream_busy"


def is_upstream_busy(e: Exception | str) -> bool:
    """Wahr, wenn der Anbieter ueberlastet war oder nicht geantwortet hat.

    Ueber den Text und nicht ueber den Typ, weil die Werkzeuge ihre Fehler aus
    drei Ecken bekommen (httpx, openai, eigene RuntimeError) und der Status nur
    im Text steht. Nimmt auch den fertigen Text, der Screencast reicht das
    ``detail`` einer HTTPException herein.
    """
    msg = str(e).lower()
    return any(m in msg for m in _BUSY_MARKERS)


def upstream_error_code(e: Exception | str) -> str | None:
    """Der Schluessel fuer die Oberflaeche, oder ``None`` wenn der Anbieter
    unschuldig ist.

    Ohne das ``None`` wuerde ein Konfigurations- oder Programmfehler als
    "versuch es spaeter" verkauft, und niemand suchte die echte Ursache.
    """
    return UPSTREAM_BUSY if is_upstream_busy(e) else None
