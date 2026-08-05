"""Erkennt, wie groß die Maschine ist, auf der KIS gerade läuft.

Ersetzt drei von Hand gepflegte Regler im Admin-Bereich. Die waren aus zwei
Gründen eine schlechte Idee. Erstens kann niemand sie beantworten: "Wie viele
parallele Plätze?" ist keine Frage über KIS, sondern eine Frage über die
Hardware, und die kennt der Rechner besser als der Mensch davor. Zweitens
veralten sie still. RENDER_MAX_WORKERS stand auf 2 mit dem Kommentar "für 4
Kerne", während die Entwicklungsmaschine 18 Kerne hat und keine Rückmeldung
kommt, dass da Leistung brachliegt.

Die Feldforschung dazu ist eindeutig. Eine Untersuchung an großer
Systemsoftware fand, dass bis zu 54 Prozent aller Einstellungen von praktisch
keinem Nutzer je gesetzt werden, und dass 48 Prozent aller Konfigurationsfehler
daher rühren, dass Leute die richtige Einstellung nicht finden oder nicht
verstehen (Xu et al., FSE 2015, "Hey, you have given me too many knobs!").

WICHTIG, die Container-Falle
----------------------------
``os.cpu_count()`` gibt im Container die Kerne des WIRTS zurück, nicht das, was
der Container benutzen darf. Das ist ein klassischer Fehler, den die JVM, Go und
Node alle einmal gemacht haben. Auf einer 64-Kern-Maschine mit ``--cpus=2``
würde KIS also 64 lesen und sich sofort selbst erwürgen.

Richtig ist, zuerst die cgroup zu fragen:
  cgroup v2: /sys/fs/cgroup/cpu.max      -> "200000 100000" heißt 2 Kerne
                                            "max 100000"    heißt unbegrenzt
             /sys/fs/cgroup/memory.max   -> Bytes, oder "max"
  cgroup v1: /sys/fs/cgroup/cpu/cpu.cfs_quota_us + cpu.cfs_period_us
             /sys/fs/cgroup/memory/memory.limit_in_bytes

Erst wenn dort nichts steht, zählt der Wirt. Zusätzlich begrenzt die
CPU-Affinität (``sched_getaffinity``), wenn jemand den Prozess an bestimmte
Kerne gebunden hat.

Die Formeln
-----------
Nachgerechnet an der Produktionsmaschine (4 Kerne, 8 GB), damit die Automatik
genau das liefert, was vorher mühsam von Hand eingestellt war:

  Gleichzeitige Uploads          min(Kerne*0,75, RAM/1 GB) -> min(3, 8) = 3
  Bild- und Videoumwandlung      Kerne/2                   -> 2

Beide stimmen mit den bisherigen Handwerten überein. Der Unterschied ist, dass
sie beim nächsten Server-Umzug von selbst mitwachsen, statt bis zum nächsten
Code-Fix falsch zu bleiben.

WAS HIER BEWUSST NICHT STEHT
----------------------------
Die Anzahl der Hintergrund-Plätze (AIA_PARALLEL_SLOTS). Die gehörte anfangs
hierher und musste wieder raus. Sie taugt nicht zur Erkennung, weil sie einen
GETEILTEN Topf beschreibt: Backend und aia-Arbeiter verteilen beide daraus, der
Arbeiter hat aber ein eigenes mem_limit und käme auf eine andere Zahl. Zwei
Prozesse mit verschiedenen Werten am selben Topf verkleinern ihn still.

Merksatz: erkennen lässt sich nur, was der eigene Prozess auch selbst verbraucht.
Uploads und Umwandlung laufen hier, deshalb passt es dort. Die Hintergrund-
Aufträge laufen woanders.

RAM steht in jeder Formel mit drin, weil Kerne allein täuschen. Eine Maschine
mit 16 Kernen und 2 GB darf trotzdem keine 12 Uploads gleichzeitig umwandeln,
LibreOffice und ffmpeg brauchen den Speicher. Der jeweils kleinere der beiden
Werte gewinnt.

Diese Datei sagt NICHTS über Anbieter-Grenzen. Wie viele Anfragen GWDG oder
myLab gleichzeitig vertragen, hat mit unseren Kernen nichts zu tun. Das sind
gemessene Konstanten in ``limits.py``.
"""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from functools import lru_cache

from loguru import logger

# Obergrenzen. Nicht als Einstellung gedacht, sondern als Schutz gegen absurde
# Ergebnisse auf sehr großen Maschinen. Über diesen Werten liegt der Engpass eh
# nicht mehr bei uns, sondern beim Anbieter oder bei der Datenbank.
_MAX_CONCURRENT_UPLOADS = 8
_MAX_RENDER_WORKERS = 8

# Wie viel Arbeitsspeicher ein einzelner Upload in der schweren Phase belegt.
# Größenordnung, nicht auf die Nachkommastelle genau: die Umwandlung startet
# LibreOffice oder ffmpeg.
_GB_PER_UPLOAD = 1.0

_BYTES_PER_GB = 1024 ** 3

# Kein Anbieter der Welt liefert eine Maschine mit weniger als einem Kern, aber
# eine kaputte cgroup-Datei könnte 0 ergeben. Dann lieber 1 als eine Division
# durch null.
_MIN_CORES = 1.0


def _read_text(path: str) -> str | None:
    try:
        with open(path, "r") as fh:
            return fh.read().strip()
    except OSError:
        return None


def _cores_from_cgroup_v2() -> float | None:
    """cpu.max enthält "QUOTA PERIOD" oder "max PERIOD" für unbegrenzt."""
    raw = _read_text("/sys/fs/cgroup/cpu.max")
    if not raw:
        return None
    parts = raw.split()
    if len(parts) != 2 or parts[0] == "max":
        return None
    try:
        quota, period = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    if quota <= 0 or period <= 0:
        return None
    return quota / period


def _cores_from_cgroup_v1() -> float | None:
    quota_raw = _read_text("/sys/fs/cgroup/cpu/cpu.cfs_quota_us")
    period_raw = _read_text("/sys/fs/cgroup/cpu/cpu.cfs_period_us")
    if not quota_raw or not period_raw:
        return None
    try:
        quota, period = int(quota_raw), int(period_raw)
    except ValueError:
        return None
    # -1 ist die ausdrückliche Schreibweise für "keine Grenze".
    if quota <= 0 or period <= 0:
        return None
    return quota / period


def _cores_from_affinity() -> float | None:
    """Nur die Kerne, auf denen dieser Prozess überhaupt laufen darf."""
    getaffinity = getattr(os, "sched_getaffinity", None)
    if getaffinity is None:
        return None
    try:
        return float(len(getaffinity(0)))
    except OSError:
        return None


def _memory_from_cgroup() -> int | None:
    """Speichergrenze des Containers in Bytes, v2 zuerst."""
    raw = _read_text("/sys/fs/cgroup/memory.max")
    if raw is None:
        raw = _read_text("/sys/fs/cgroup/memory/memory.limit_in_bytes")
    if not raw or raw == "max":
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    # cgroup v1 schreibt für "unbegrenzt" eine absurd große Zahl (nahe 2^63)
    # statt "max". Alles jenseits von 1 PB ist offensichtlich keine echte
    # Grenze, sondern genau dieser Platzhalter.
    if value <= 0 or value > 1024 ** 5:
        return None
    return value


def _memory_from_host() -> int | None:
    raw = _read_text("/proc/meminfo")
    if raw:
        for line in raw.splitlines():
            if line.startswith("MemTotal:"):
                try:
                    return int(line.split()[1]) * 1024
                except (IndexError, ValueError):
                    break
    # macOS und alles andere ohne /proc. sysconf kennt die Seitenzahl.
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (OSError, ValueError, AttributeError):
        return None


@dataclass(frozen=True)
class Capacity:
    """Was die Maschine hergibt und was KIS daraus ableitet."""

    cores: float
    memory_bytes: int
    # Woher die Werte stammen, damit die Auslastungsanzeige ehrlich sagen kann
    # "Container-Grenze" statt so zu tun, als hätte sie den Wirt gemessen.
    cores_source: str
    memory_source: str

    @property
    def memory_gb(self) -> float:
        return self.memory_bytes / _BYTES_PER_GB

    def _by_cores_and_memory(self, per_core: float, gb_each: float, ceiling: int) -> int:
        by_cores = self.cores * per_core
        by_memory = self.memory_gb / gb_each
        return max(1, min(ceiling, int(math.floor(min(by_cores, by_memory)))))

    @property
    def max_concurrent_uploads(self) -> int:
        """Gleichzeitige Uploads in der schweren Phase (streamen, umwandeln, ablegen)."""
        return self._by_cores_and_memory(0.75, _GB_PER_UPLOAD, _MAX_CONCURRENT_UPLOADS)

    @property
    def render_workers(self) -> int:
        """Threads für PDF nach PNG und ffmpeg. Rein rechenlastig, RAM ist hier
        nicht der Engpass, deshalb als einzige Formel ohne Speicheranteil."""
        return max(1, min(_MAX_RENDER_WORKERS, int(math.floor(self.cores / 2))))

    def as_dict(self) -> dict:
        return {
            "cores": round(self.cores, 2),
            "cores_source": self.cores_source,
            "memory_bytes": self.memory_bytes,
            "memory_gb": round(self.memory_gb, 2),
            "memory_source": self.memory_source,
            "max_concurrent_uploads": self.max_concurrent_uploads,
            "render_workers": self.render_workers,
        }


def _detect() -> Capacity:
    cores: float | None = None
    cores_source = "unbekannt"
    for source, fn in (
        ("cgroup v2", _cores_from_cgroup_v2),
        ("cgroup v1", _cores_from_cgroup_v1),
        ("CPU-Affinität", _cores_from_affinity),
    ):
        cores = fn()
        if cores:
            cores_source = source
            break
    if not cores:
        cores = float(os.cpu_count() or 1)
        cores_source = "Wirtssystem"

    memory = _memory_from_cgroup()
    memory_source = "Container-Grenze"
    if memory is None:
        memory = _memory_from_host()
        memory_source = "Wirtssystem"
    if memory is None:
        # Letzte Rückfallebene. Bewusst klein gewählt: wenn wir nichts wissen,
        # ist Vorsicht richtig, ein zu großer Schätzwert würde die Maschine
        # überlasten statt sie nur langsam zu machen.
        memory = 2 * _BYTES_PER_GB
        memory_source = "Schätzwert"

    return Capacity(
        cores=max(_MIN_CORES, cores),
        memory_bytes=memory,
        cores_source=cores_source,
        memory_source=memory_source,
    )


@lru_cache(maxsize=1)
def capacity() -> Capacity:
    """Die erkannte Maschine. Einmal je Prozess, danach aus dem Zwischenspeicher.

    Nicht bei jedem Aufruf neu zu lesen ist Absicht: Kerne und Speichergrenze
    ändern sich nicht im laufenden Betrieb, und die Werte werden in heißen
    Pfaden gebraucht (jeder Upload, jeder Auftrag).
    """
    result = _detect()
    logger.info(
        "Maschine erkannt: {:.2f} Kerne ({}), {:.1f} GB ({}) "
        "-> Uploads {}, Umwandlung {}",
        result.cores, result.cores_source,
        result.memory_gb, result.memory_source,
        result.max_concurrent_uploads, result.render_workers,
    )
    return result
