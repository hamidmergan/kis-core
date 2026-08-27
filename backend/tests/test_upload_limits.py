"""The hourly limit counts accepted uploads only, a rejection costs nothing."""
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
    """Just enough of the redis client surface for the upload limit helpers."""

    def __init__(self, store):
        self._store = store

    def pipeline(self):
        return _FakePipeline(self._store)

    def get(self, key):
        return self._store.get(key)

    def ttl(self, key):
        return 1800

    def close(self):
        pass


@pytest.fixture
def fake_redis(monkeypatch):
    store: dict[str, int] = {}
    monkeypatch.setattr(rate_limit, "_redis", lambda: _FakeRedis(store))
    return store


def test_uploads_allowed_up_to_cap(fake_redis):
    """check passes and record counts, up to exactly the hourly cap."""
    for _ in range(UPLOAD_HOURLY_MAX):
        rate_limit.check_upload_limit(user_id=42)   # must not raise
        rate_limit.record_upload(user_id=42)
    assert fake_redis["rl:upload:hourly:42"] == UPLOAD_HOURLY_MAX


def test_check_rejects_when_cap_full(fake_redis):
    for _ in range(UPLOAD_HOURLY_MAX):
        rate_limit.record_upload(user_id=7)
    with pytest.raises(HTTPException) as exc:
        rate_limit.check_upload_limit(user_id=7)
    assert exc.value.status_code == 429
    assert exc.value.detail["kind"] == "upload_hourly"


def test_failed_upload_does_not_consume_quota(fake_redis):
    """A rejected upload checks but does not count."""
    for _ in range(UPLOAD_HOURLY_MAX * 3):
        rate_limit.check_upload_limit(user_id=9)    # route would then raise -> no record
    assert fake_redis.get("rl:upload:hourly:9", 0) == 0
    # And a real upload right after still goes through.
    rate_limit.check_upload_limit(user_id=9)
    rate_limit.record_upload(user_id=9)
    assert fake_redis["rl:upload:hourly:9"] == 1


def test_check_does_not_increment(fake_redis):
    """Pure read: repeated checks under the cap never change the counter."""
    rate_limit.record_upload(user_id=5)             # one real upload
    for _ in range(10):
        rate_limit.check_upload_limit(user_id=5)
    assert fake_redis["rl:upload:hourly:5"] == 1


def test_admin_bypass(fake_redis):
    for _ in range(UPLOAD_HOURLY_MAX * 2):
        rate_limit.check_upload_limit(user_id=0)    # user_id <= 0 is a no-op
        rate_limit.record_upload(user_id=0)
    assert "rl:upload:hourly:0" not in fake_redis
