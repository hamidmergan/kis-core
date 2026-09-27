"""Seats at a provider, shared by every worker, so requests wait with us instead of failing there."""

from __future__ import annotations

import os
import random
import time
import uuid
from contextlib import contextmanager

from loguru import logger

_REDIS_URL = os.environ.get("REDIS_URL", "redis://kis-redis:6379/0")
_KEY = "kis:provider-slots:{}"

# A seat older than this belongs to a worker that died mid request and is freed.
STALE_SECONDS = 5 * 60


class ProviderFull(RuntimeError):
    """No seat came free in time, worded so that it counts as a full provider (503)."""

    def __init__(self, provider: str, waited: float):
        super().__init__(f"503 service unavailable: provider {provider} full, waited {waited:.0f}s")


def _redis():
    import redis as _redis_lib
    return _redis_lib.from_url(_REDIS_URL, socket_connect_timeout=1, socket_timeout=2)


def claim(provider: str, *, limit: int, wait_seconds: float, r=None) -> str:
    """Takes a seat, waiting up to wait_seconds, and raises ProviderFull when none came free."""
    ticket = uuid.uuid4().hex
    key = _KEY.format(provider)
    start = time.time()
    try:
        r = r if r is not None else _redis()
        while True:
            now = time.time()
            r.zremrangebyscore(key, "-inf", now - STALE_SECONDS)
            # Sit down first, then count, so two workers can never both slip past the limit.
            r.zadd(key, {ticket: now})
            if r.zcard(key) <= limit:
                return ticket
            r.zrem(key, ticket)
            if now - start >= wait_seconds:
                raise ProviderFull(provider, now - start)
            time.sleep(0.5 + random.random())
    except ProviderFull:
        raise
    except Exception as e:  # noqa: BLE001 - without Redis the request goes through unbraked
        logger.warning("Anbieter-Plätze nicht erreichbar (Redis), lasse durch: {}", e)
        return ticket


def release(provider: str, ticket: str, r=None) -> None:
    try:
        (r if r is not None else _redis()).zrem(_KEY.format(provider), ticket)
    except Exception as e:  # noqa: BLE001 - the seat drops out by itself after STALE_SECONDS
        logger.warning("Anbieter-Platz nicht freigegeben: {}", e)


@contextmanager
def slot(provider: str, *, limit: int, wait_seconds: float, r=None):
    """A seat for the duration of one request, given back even when the request fails."""
    ticket = claim(provider, limit=limit, wait_seconds=wait_seconds, r=r)
    try:
        yield
    finally:
        release(provider, ticket, r=r)
