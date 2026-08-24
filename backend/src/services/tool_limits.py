"""Grenzen der globalen Werkzeuge, zur Laufzeit statt fest im Code.

Warum ueberhaupt Funktionen und keine Konstanten mehr: die Zahlen in
``limits.py`` werden BEIM START importiert. Ein im Admin geaenderter Wert wuerde
damit erst nach einem Neustart aller Container greifen, was im Betrieb niemand
tut, nur um von 50 auf 60 Folien zu gehen. Diese Funktionen lesen bei jeder
Anfrage, die Konstante bleibt die Vorgabe.

WELCHE Grenze hierher gehoert, entscheidet eine einzige Frage: haengt der
richtige Wert von der Nutzung der Hochschule ab oder von der Technik? Wie lang
Vorlesungen sind und wie gross Foliensaetze werden, weiss nur die Hochschule.
Wie lang ein Stueck beim Zerlegen sein darf (9 Minuten) oder wie viele Zeichen
in eine Sprachanfrage passen (400), ist gemessen und steht weiter fest in
``limits.py``. Dieselbe Trennlinie zieht ``services/system_capacity.py`` fuer
alles, was an Kernen und Speicher haengt.

``-1`` heisst unbegrenzt, aber nur bei den beiden Zaehlgrenzen. Bei Folienzahl,
Aufnahmelaenge und Dateigroesse waere es eine Falle: der Auftrag laeuft in die
Zeitgrenze, der Anbieter lehnt ab, die Platte laeuft voll. Dort ist eine hohe
Obergrenze ehrlicher als ein Unendlich, das dann doch scheitert.
"""

from loguru import logger

from src import database as db
from src.limits import (
    MAX_AUDIO_SEC,
    MAX_QUEUED_SCREENCAST_JOBS,
    MAX_RESULT_FILES,
    MAX_SCREENCAST_SLIDES,
    MAX_UPLOAD_BYTES,
)

_BYTES_PER_MB = 1024 * 1024

# Nur diese beiden duerfen unbegrenzt sein.
UNBEGRENZT = -1
_DARF_UNBEGRENZT = frozenset({"results_kept_per_user", "screencast_max_open_jobs"})


def _zahl(key: str, vorgabe: int) -> int:
    """Eintrag lesen, alles Unbrauchbare faellt auf die Vorgabe zurueck.

    Ein kaputter Eintrag darf kein Werkzeug lahmlegen. Er kann nur ueber die
    Admin-Oberflaeche entstehen, die selbst schon Grenzen prueft, aber die
    Tabelle ``settings`` ist auch von Hand beschreibbar.
    """
    roh = db.get_setting(key, "")
    if not roh:
        return vorgabe
    try:
        wert = int(str(roh).strip())
    except (TypeError, ValueError):
        logger.warning("Einstellung {} ist keine Zahl ({!r}), nehme {}", key, roh, vorgabe)
        return vorgabe
    if wert == UNBEGRENZT and key in _DARF_UNBEGRENZT:
        return UNBEGRENZT
    if wert < 1:
        logger.warning("Einstellung {} ist {}, nehme {}", key, wert, vorgabe)
        return vorgabe
    return wert


def max_screencast_slides() -> int:
    """Folien je Screencast."""
    return _zahl("screencast_max_slides", MAX_SCREENCAST_SLIDES)


def max_transcription_seconds() -> int:
    """Laenge einer Aufnahme. Im Admin stehen Minuten, gerechnet wird in Sekunden."""
    minuten = _zahl("transcription_max_minutes", MAX_AUDIO_SEC // 60)
    return minuten * 60


def max_upload_bytes() -> int:
    """Groesse einer hochgeladenen Datei. Im Admin stehen MB."""
    return _zahl("upload_max_mb", MAX_UPLOAD_BYTES // _BYTES_PER_MB) * _BYTES_PER_MB


def results_kept_per_user() -> int:
    """Aufbewahrte Auftraege je Person, ``-1`` heisst unbegrenzt.

    Die einzige Aufraeumregel, seit die Frist von sieben Tagen raus ist.
    """
    return _zahl("results_kept_per_user", MAX_RESULT_FILES)


def max_open_screencast_jobs() -> int:
    """Offene Screencast-Auftraege je Person, ``-1`` heisst unbegrenzt."""
    return _zahl("screencast_max_open_jobs", MAX_QUEUED_SCREENCAST_JOBS)
