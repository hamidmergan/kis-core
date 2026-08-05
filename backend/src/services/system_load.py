"""Misst, wie ausgelastet die Maschine GERADE ist.

Abgegrenzt von ``system_capacity.py``: das dort ist statisch (wie groß ist die
Maschine), das hier ist dynamisch (wie voll ist sie in dieser Sekunde). Beides
in eine Datei zu werfen hieße, einen Zwischenspeicher zu bauen, der mal gilt und
mal nicht.

Gebraucht wird das, weil die Auslastung bisher NIRGENDS sichtbar war. Man konnte
im Admin-Bereich drei parallele Plätze einstellen und hat nie erfahren, ob drei
reicht. Genau das macht solche Regler so unbefriedigend: eine Zahl eingeben, die
man nicht begründen kann, und danach keine Rückmeldung bekommen.

Im Container zählt die cgroup, nicht der Wirt. ``/proc/loadavg`` und
``/proc/meminfo`` zeigen die Werte der ganzen Maschine, auch wenn der Container
nur zwei Kerne davon benutzen darf. Auf einem geteilten Wirt wäre die Anzeige
damit schlicht falsch. Deshalb zuerst ``cpu.stat`` und ``memory.current`` der
eigenen cgroup, und erst danach die Sicht auf den Wirt.
"""

from __future__ import annotations

import asyncio
import os
import time

from src.services.system_capacity import capacity

# Abstand zwischen den beiden Messpunkten der CPU-Messung. Prozessorlast lässt
# sich nur als Differenz zweier Zeitpunkte bestimmen, ein Einzelwert existiert
# nicht. 300 ms ist der Kompromiss: kürzer wird der Wert zappelig, länger
# spürt man die Wartezeit beim Öffnen der Seite.
_SAMPLE_SECONDS = 0.3


def _read_text(path: str) -> str | None:
    try:
        with open(path, "r") as fh:
            return fh.read().strip()
    except OSError:
        return None


def _cgroup_cpu_usec() -> int | None:
    """Verbrauchte Prozessorzeit dieser cgroup in Mikrosekunden, seit Start."""
    raw = _read_text("/sys/fs/cgroup/cpu.stat")
    if raw:
        for line in raw.splitlines():
            if line.startswith("usage_usec"):
                try:
                    return int(line.split()[1])
                except (IndexError, ValueError):
                    return None
    raw = _read_text("/sys/fs/cgroup/cpuacct/cpuacct.usage")  # cgroup v1, Nanosekunden
    if raw:
        try:
            return int(raw) // 1000
        except ValueError:
            return None
    return None


async def cpu_percent() -> float | None:
    """Auslastung in Prozent der VERFÜGBAREN Kerne, nicht der Kerne des Wirts.

    100 Prozent heißt also "die Maschine ist am Anschlag", egal ob sie zwei oder
    zwanzig Kerne hat. Ohne cgroup (Entwicklung auf macOS) fällt die Messung auf
    die Lastmittelwerte zurück, die sind gröber, aber besser als nichts.
    """
    first = _cgroup_cpu_usec()
    if first is not None:
        # asyncio.sleep und nicht time.sleep: die Route ist async, ein
        # blockierendes Warten würde alle anderen Anfragen mit anhalten.
        await asyncio.sleep(_SAMPLE_SECONDS)
        second = _cgroup_cpu_usec()
        if second is not None and second >= first:
            used_seconds = (second - first) / 1_000_000
            available_seconds = _SAMPLE_SECONDS * capacity().cores
            if available_seconds > 0:
                return round(min(100.0, used_seconds / available_seconds * 100), 1)
        return None
    try:
        one_minute = os.getloadavg()[0]
    except (OSError, AttributeError):
        return None
    return round(min(100.0, one_minute / capacity().cores * 100), 1)


def memory_used_bytes() -> int | None:
    raw = _read_text("/sys/fs/cgroup/memory.current")
    if raw is None:
        raw = _read_text("/sys/fs/cgroup/memory/memory.usage_in_bytes")
    if raw:
        try:
            return int(raw)
        except ValueError:
            pass
    meminfo = _read_text("/proc/meminfo")
    if meminfo:
        total = available = None
        for line in meminfo.splitlines():
            if line.startswith("MemTotal:"):
                total = int(line.split()[1]) * 1024
            elif line.startswith("MemAvailable:"):
                available = int(line.split()[1]) * 1024
            if total is not None and available is not None:
                return max(0, total - available)
    return None


def job_slots() -> dict:
    """Belegte und wartende Hintergrundplätze.

    Kommt aus der Tabelle ``aia_jobs``, die diese Zustände ohnehin führt. Es
    braucht dafür keinen neuen Zähler, der auseinanderlaufen könnte.
    """
    from src.limits import AIA_PARALLEL_SLOTS
    from src.features.ai_assistant.repository.jobs import DbJobStore

    store = DbJobStore()
    running = store.running_all()
    queued = store.queued_all()
    by_area: dict[str, int] = {}
    for _user_id, area in running:
        by_area[area] = by_area.get(area, 0) + 1
    return {
        "total": AIA_PARALLEL_SLOTS,
        "running": len(running),
        "queued": len(queued),
        "running_by_area": by_area,
    }


def upload_slots() -> dict:
    """Laufende Uploads in der schweren Phase (streamen, umwandeln, ablegen)."""
    from src.features.ai_assistant.routes.sources import _upload

    in_flight = None
    try:
        r = _upload._redis()
        now = time.time()
        r.zremrangebyscore(_upload._UPLOAD_SET_KEY, "-inf", now - _upload._UPLOAD_STALE_SECONDS)
        in_flight = int(r.zcard(_upload._UPLOAD_SET_KEY))
    except Exception:
        pass
    return {"total": _upload._max_concurrent_uploads(), "running": in_flight}
