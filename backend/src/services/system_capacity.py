"""Detects the machine size, in a container via the cgroup instead of the host."""

from __future__ import annotations

import math
import os
from dataclasses import dataclass
from functools import lru_cache

from loguru import logger

# Ceilings as a guard against absurd results on very large machines.
_MAX_CONCURRENT_UPLOADS = 8
_MAX_RENDER_WORKERS = 8

# How much memory a single upload takes in the heavy phase.
_GB_PER_UPLOAD = 1.0
# One ffmpeg clip takes about 0.3 GB, doubled because the worker renders two jobs at once.
_GB_PER_RENDER_WORKER = 1.0

_BYTES_PER_GB = 1024 ** 3

# A broken cgroup file could yield 0, then rather 1.
_MIN_CORES = 1.0


def _read_text(path: str) -> str | None:
    try:
        with open(path, "r") as fh:
            return fh.read().strip()
    except OSError:
        return None


def _cores_from_cgroup_v2() -> float | None:
    """cpu.max holds 'QUOTA PERIOD' or 'max PERIOD' for unlimited."""
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
    # -1 is the explicit spelling for 'no limit'.
    if quota <= 0 or period <= 0:
        return None
    return quota / period


def _cores_from_affinity() -> float | None:
    """Only the cores this process is actually allowed to run on."""
    getaffinity = getattr(os, "sched_getaffinity", None)
    if getaffinity is None:
        return None
    try:
        return float(len(getaffinity(0)))
    except OSError:
        return None


def _memory_from_cgroup() -> int | None:
    """Memory limit of the container in bytes, v2 first."""
    raw = _read_text("/sys/fs/cgroup/memory.max")
    if raw is None:
        raw = _read_text("/sys/fs/cgroup/memory/memory.limit_in_bytes")
    if not raw or raw == "max":
        return None
    try:
        value = int(raw)
    except ValueError:
        return None
    # cgroup v1 writes an absurdly large number instead of 'max' for unlimited.
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
    # macOS and everything else without /proc, sysconf knows the page count.
    try:
        return os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
    except (OSError, ValueError, AttributeError):
        return None


@dataclass(frozen=True)
class Capacity:
    """What the machine offers and what askFrancis derives from it."""

    cores: float
    memory_bytes: int
    # Where the values come from, so the display stays honest.
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
        """Concurrent uploads in the heavy phase (stream, convert, store)."""
        return self._by_cores_and_memory(0.75, _GB_PER_UPLOAD, _MAX_CONCURRENT_UPLOADS)

    @property
    def render_workers(self) -> int:
        """Threads for PDF to PNG and ffmpeg, half the cores and bounded by memory."""
        return self._by_cores_and_memory(0.5, _GB_PER_RENDER_WORKER, _MAX_RENDER_WORKERS)

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
        # Letzte Rueckfallebene, bewusst klein gewaehlt.
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
    """The detected machine, read once per process and then cached."""
    result = _detect()
    logger.info(
        "Maschine erkannt: {:.2f} Kerne ({}), {:.1f} GB ({}) "
        "-> Uploads {}, Umwandlung {}",
        result.cores, result.cores_source,
        result.memory_gb, result.memory_source,
        result.max_concurrent_uploads, result.render_workers,
    )
    return result
