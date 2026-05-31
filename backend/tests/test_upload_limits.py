"""Upload rate-limit behaviour.

Locks in the design decision that source uploads have NO concurrent in-flight
cap (backpressure lives in the Celery worker). The only HTTP-level throttle is
the hourly window; the per-workspace ceiling is enforced separately in the
route, not here.
"""
import pytest
from fastapi import HTTPException

from src.security import rate_limit
from src.limits import UPLOAD_HOURLY_MAX


class _FakePipeline:
    def __init__(self, store):
        self._store = store
        self._key = None

    def incr(self, key):
        self._key = key
        self._store[key] = self._store.get(key, 0) + 1
        return self

    def expire(self, key, seconds, nx=False):
        return self

    def execute(self):
        return [self._store[self._key], True]


class _FakeRedis:
    """Just enough of the redis client surface for enforce_upload_limits."""

    def __init__(self, store):
        self._store = store

    def pipeline(self):
        return _FakePipeline(self._store)

    def decr(self, key):
        self._store[key] = self._store.get(key, 0) - 1

    def ttl(self, key):
        return 1800

    def close(self):
        pass


@pytest.fixture
def fake_redis(monkeypatch):
    store: dict[str, int] = {}
    monkeypatch.setattr(rate_limit, "_redis", lambda: _FakeRedis(store))
    return store


def test_no_concurrent_cap_many_uploads_accepted(fake_redis):
    """Firing well past the old concurrent cap (10) never raises on its own.

    Before the redesign the 11th in-flight upload got a 429; now only the
    hourly window can reject, so a burst stays accepted until that window fills.
    """
    for _ in range(UPLOAD_HOURLY_MAX):
        rate_limit.enforce_upload_limits(user_id=42)  # must not raise


def test_hourly_cap_still_rejects(fake_redis):
    for _ in range(UPLOAD_HOURLY_MAX):
        rate_limit.enforce_upload_limits(user_id=7)
    with pytest.raises(HTTPException) as exc:
        rate_limit.enforce_upload_limits(user_id=7)
    assert exc.value.status_code == 429
    assert exc.value.detail["kind"] == "upload_hourly"


def test_rejected_upload_does_not_consume_quota(fake_redis):
    """An over-limit attempt rolls the counter back so the next hour is clean."""
    for _ in range(UPLOAD_HOURLY_MAX):
        rate_limit.enforce_upload_limits(user_id=9)
    with pytest.raises(HTTPException):
        rate_limit.enforce_upload_limits(user_id=9)
    # Counter must sit exactly at the cap, not above it.
    assert fake_redis["rl:upload:hourly:9"] == UPLOAD_HOURLY_MAX


def test_admin_bypass(fake_redis):
    for _ in range(UPLOAD_HOURLY_MAX * 2):
        rate_limit.enforce_upload_limits(user_id=0)  # user_id <= 0 is a no-op
