"""Distributed weighted rate gate shared across backend + workers via Redis.

One scarce budget (global calls/sec) split across areas by weight. Each area
gets its own token bucket sized ``rate_i = global * weight_i / sum(weights)``,
so every area keeps a guaranteed minimum share and none is starved. Callers
- synchronous chat in the backend, celery workers for ingest/studio - all check
the same Redis-backed buckets before making a provider call.

``global_per_sec <= 0`` means unlimited (the GPU future): the gate becomes a
no-op so nothing waits.

Not work-conserving yet: an idle area's share is not lent out. That overflow
refinement is a deliberate follow-up. Cross-process atomicity of the token
maths is also a known follow-up (a Lua CAS); under the demo's light contention
the occasional double-grant is negligible and the split still holds.
"""
from __future__ import annotations

import time
from typing import Callable, Optional

from .rate_gate import AtomicRedisLimiter, BucketStore, InMemoryStore, RateGate


def area_rates(global_per_sec: float, weights: dict[str, float]) -> dict[str, float]:
    """Split a global rate across areas by weight. 0 global -> all unlimited (0)."""
    total = sum(w for w in weights.values() if w > 0)
    if total <= 0 or global_per_sec <= 0:
        return {a: 0.0 for a in weights}
    return {a: global_per_sec * (w / total) for a, w in weights.items()}


class _AcquireMixin:
    """Shared blocking/async wait loops on top of a subclass ``allow(area)``."""

    def allow(self, area: str) -> bool:  # pragma: no cover - implemented by subclass
        raise NotImplementedError

    def acquire(
        self,
        area: str,
        max_wait: float = 30.0,
        sleep: Callable[[float], None] = time.sleep,
        now: Callable[[], float] = time.monotonic,
    ) -> bool:
        """Block until a token is free for ``area`` or ``max_wait`` elapses.

        Used by the synchronous (worker) call sites. Returns True if granted,
        False on timeout (caller then proceeds anyway rather than hang)."""
        if self.allow(area):
            return True
        deadline = now() + max_wait
        while now() < deadline:
            sleep(0.05)
            if self.allow(area):
                return True
        return False

    async def acquire_async(self, area: str, max_wait: float = 30.0) -> bool:
        """Async variant for the synchronous-but-async chat path. Awaits without
        blocking the event loop."""
        import asyncio

        if self.allow(area):
            return True
        deadline = time.monotonic() + max_wait
        while time.monotonic() < deadline:
            await asyncio.sleep(0.05)
            if self.allow(area):
                return True
        return False


class WeightedGate(_AcquireMixin):
    """In-memory / single-process gate. Used by tests and the simulator."""

    def __init__(
        self,
        global_per_sec: float,
        weights: dict[str, float],
        store: Optional[BucketStore] = None,
        now: Callable[[], float] = time.time,
        burst: Optional[float] = None,
    ) -> None:
        self.global_per_sec = float(global_per_sec)
        self.weights = dict(weights)
        self._unlimited = self.global_per_sec <= 0
        shared = store if store is not None else InMemoryStore()
        rates = area_rates(self.global_per_sec, self.weights)
        self._gates: dict[str, RateGate] = {
            area: RateGate(
                rate,
                burst if burst is not None else max(1.0, rate),
                store=shared,
                now=now,
            )
            for area, rate in rates.items()
        }

    def allow(self, area: str) -> bool:
        if self._unlimited:
            return True
        gate = self._gates.get(area)
        if gate is None:
            return True  # unknown area is never blocked
        return gate.allow(area)


class RedisWeightedGate(_AcquireMixin):
    """Cross-process gate using an atomic Lua token bucket per area. This is the
    production path: concurrent backend + workers cannot over-grant."""

    def __init__(
        self,
        global_per_sec: float,
        weights: dict[str, float],
        client=None,
        burst: Optional[float] = None,
    ) -> None:
        self.global_per_sec = float(global_per_sec)
        self.weights = dict(weights)
        self._unlimited = self.global_per_sec <= 0
        self._rates = area_rates(self.global_per_sec, self.weights)
        self._burst = burst
        self._limiter = None if self._unlimited else AtomicRedisLimiter(client)

    def allow(self, area: str) -> bool:
        if self._unlimited:
            return True
        rate = self._rates.get(area)
        if rate is None:
            return True
        burst = self._burst if self._burst is not None else max(1.0, rate)
        return self._limiter.allow(area, rate, burst)
