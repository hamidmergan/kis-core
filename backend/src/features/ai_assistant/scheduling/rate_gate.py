"""Configurable token-bucket rate gate, keyed per provider.

The global bottleneck on outbound AI calls. Each key (provider) has its own
bucket refilling at ``rate_per_sec`` up to ``burst``. ``rate_per_sec <= 0``
disables throttling entirely -- the GPU future where there is no 2/s rule, set
the rate setting to 0 and the gate becomes a no-op.

State lives in an injectable store so the policy is unit-testable in memory.
Across processes (backend + workers) production uses ``RedisStore`` which keeps
the bucket in a Redis hash. The refill maths is identical either way.
"""
from __future__ import annotations

import os
import time
from typing import Callable, Optional, Protocol


class BucketStore(Protocol):
    def get(self, key: str) -> Optional[tuple[float, float]]: ...
    def set(self, key: str, tokens: float, ts: float) -> None: ...


class InMemoryStore:
    """Single-process bucket store. Used by tests and the in-process stress run."""

    def __init__(self) -> None:
        self._d: dict[str, tuple[float, float]] = {}

    def get(self, key: str) -> Optional[tuple[float, float]]:
        return self._d.get(key)

    def set(self, key: str, tokens: float, ts: float) -> None:
        self._d[key] = (tokens, ts)


class RedisStore:
    """Cross-process bucket store backed by a Redis hash per key.

    Not exercised by unit tests (needs a live Redis), but mirrors InMemoryStore
    so the RateGate maths is identical in production.
    """

    def __init__(self, client=None, prefix: str = "aia:rategate:") -> None:
        if client is None:
            import redis

            client = redis.from_url(
                os.environ.get("REDIS_URL", "redis://kis-redis:6379/0")
            )
        self._r = client
        self._prefix = prefix

    def get(self, key: str) -> Optional[tuple[float, float]]:
        raw = self._r.hgetall(self._prefix + key)
        if not raw:
            return None
        tokens = float(raw[b"tokens"] if b"tokens" in raw else raw["tokens"])
        ts = float(raw[b"ts"] if b"ts" in raw else raw["ts"])
        return (tokens, ts)

    def set(self, key: str, tokens: float, ts: float) -> None:
        self._r.hset(self._prefix + key, mapping={"tokens": tokens, "ts": ts})
        self._r.expire(self._prefix + key, 3600)


class RateGate:
    def __init__(
        self,
        rate_per_sec: float,
        burst: float,
        store: Optional[BucketStore] = None,
        now: Callable[[], float] = time.monotonic,
    ) -> None:
        self.rate = float(rate_per_sec)
        self.burst = float(burst)
        self.store: BucketStore = store if store is not None else InMemoryStore()
        self.now = now

    def allow(self, key: str) -> bool:
        """Consume one token for ``key`` if available. rate <= 0 means unlimited."""
        if self.rate <= 0:
            return True
        now = self.now()
        state = self.store.get(key)
        if state is None:
            tokens = self.burst
        else:
            tokens, last = state
            tokens = min(self.burst, tokens + (now - last) * self.rate)
        if tokens >= 1.0:
            self.store.set(key, tokens - 1.0, now)
            return True
        self.store.set(key, tokens, now)
        return False


def gate_for_provider(
    provider: str,
    store: Optional[BucketStore] = None,
    get_setting: Optional[Callable[..., str]] = None,
    now: Callable[[], float] = time.monotonic,
) -> RateGate:
    """Build a RateGate for ``provider`` from admin settings.

    Setting keys (admin-tunable, live):
      ``aia_rate_<provider>_per_sec``  default "2"  (0 = unlimited)
      ``aia_rate_<provider>_burst``    default "2"
    """
    if get_setting is None:
        from src.features.admin.repository.settings import get_setting as _gs

        get_setting = _gs
    rate = float(get_setting(f"aia_rate_{provider}_per_sec", "2"))
    burst = float(get_setting(f"aia_rate_{provider}_burst", "2"))
    return RateGate(rate, burst, store=store, now=now)
