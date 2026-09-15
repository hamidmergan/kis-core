"""A new voicing run must not die on the cancel mark of the previous one."""

import pytest

from src.tasks.podcast_tasks import _shared


class _FakeRedis:
    def __init__(self, marken=()):
        self.marken = set(marken)
        self.geloescht = []

    def exists(self, key):
        return key in self.marken

    def delete(self, key):
        self.geloescht.append(key)
        self.marken.discard(key)


@pytest.fixture
def _redis(monkeypatch):
    fake = _FakeRedis({"job:cancel:abc"})
    monkeypatch.setattr(_shared, "_r", fake)
    return fake


def test_the_mark_of_a_cancelled_run_is_cleared(_redis):
    _shared.clear_cancel("abc")
    assert _redis.geloescht == ["job:cancel:abc"]


def test_after_clearing_the_run_is_no_longer_cancelled(_redis):
    _shared.clear_cancel("abc")
    _shared.assert_not_cancelled("abc")


def test_without_clearing_the_run_still_stops(_redis):
    with pytest.raises(_shared.JobCancelled):
        _shared.assert_not_cancelled("abc")


def test_a_broken_redis_does_not_block_the_start(monkeypatch):
    class _Kaputt:
        def delete(self, key):
            import redis
            raise redis.RedisError("weg")

    monkeypatch.setattr(_shared, "_r", _Kaputt())
    _shared.clear_cancel("abc")
