"""The storage side of the stamp card: stamps committed once, wrong tries counted in Redis, fail-open."""
from datetime import datetime

import pytest

from src.features.event import repository as repo
from src.features.event.service import default_task_card
from src.limits import EVENT_CODE_LOCK_SECONDS, EVENT_CODE_MAX_ATTEMPTS

HASH = "a" * 64
JETZT = 1_700_000_000_000


class _FakeCursor:
    def __init__(self, rows, calls):
        self._rows = list(rows)
        self._calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self._calls.append(("execute", " ".join(sql.split()), params))

    def fetchone(self):
        return self._rows.pop(0) if self._rows else None

    def fetchall(self):
        return list(self._rows)


class _FakeConn:
    def __init__(self, rows, calls):
        self._rows = rows
        self._calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self, **kwargs):
        return _FakeCursor(self._rows, self._calls)

    def commit(self):
        self._calls.append(("commit", None, None))


@pytest.fixture
def fake_db(monkeypatch):
    def _apply(rows=()):
        calls: list[tuple] = []
        monkeypatch.setattr(repo, "get_connection", lambda: _FakeConn(rows, calls))
        return calls
    return _apply


class FakeRedis:
    """Just enough of the client for the counter and the lock, values come back as bytes like the real one."""

    def __init__(self, store: dict):
        self.store = store

    def get(self, key):
        wert = self.store.get(key)
        return None if wert is None else str(wert).encode()

    def incr(self, key):
        self.store[key] = int(self.store.get(key, 0)) + 1
        return self.store[key]

    def expire(self, key, seconds, nx=False):
        return True

    def set(self, key, value, ex=None):
        self.store[key] = value

    def delete(self, *keys):
        for key in keys:
            self.store.pop(key, None)

    def close(self):
        pass


@pytest.fixture
def fake_redis(monkeypatch):
    store: dict = {}
    monkeypatch.setattr(repo, "_redis", lambda: FakeRedis(store))
    return store


@pytest.fixture
def broken_redis(monkeypatch):
    def _kaputt():
        raise ConnectionError("Redis weg")
    monkeypatch.setattr(repo, "_redis", _kaputt)


# --- configuration --------------------------------------------------------------

def test_an_unsaved_configuration_is_the_seed(monkeypatch):
    monkeypatch.setattr(repo, "get_setting", lambda key, default="": "")
    assert repo.get_config()["stations"][0]["id"] == "management"


def test_a_saved_configuration_wins_over_the_seed(monkeypatch):
    monkeypatch.setattr(repo, "get_setting", lambda key, default="": '{"stations": [], "eventBlock": {}}')
    assert repo.get_config() == {
        "stations": [], "eventBlock": {}, "hideCodeOnPosters": False, "taskCard": default_task_card(),
    }


def test_a_saved_hide_setting_is_kept(monkeypatch):
    monkeypatch.setattr(
        repo, "get_setting", lambda key, default="": '{"stations": [], "eventBlock": {}, "hideCodeOnPosters": true}'
    )
    assert repo.get_config()["hideCodeOnPosters"] is True


def test_saving_writes_json_under_the_one_key(monkeypatch):
    geschrieben = {}
    monkeypatch.setattr(repo, "set_setting", lambda key, value: geschrieben.__setitem__(key, value))
    repo.save_config({"stations": [], "eventBlock": {"heading": {"de": "Tag der Lehre", "en": ""}}})
    assert set(geschrieben) == {"event_config"}
    assert "Tag der Lehre" in geschrieben["event_config"]


# --- stamps ---------------------------------------------------------------------

def test_a_stamp_is_written_once_and_committed(fake_db):
    calls = fake_db()
    repo.add_stamp(HASH, "study")
    anweisungen = [c[1] for c in calls if c[0] == "execute"]
    assert any("ON CONFLICT DO NOTHING" in a for a in anweisungen), "sonst knallt der zweite Besuch"
    assert ("commit", None, None) in calls


def test_stamps_come_back_as_epoch_milliseconds(fake_db):
    """The naive database timestamp is read as UTC, 2026-11-13 10:00 UTC is 1 794 564 000 s."""
    fake_db(rows=[("study", datetime(2026, 11, 13, 10, 0, 0))])
    assert repo.stamps_for(HASH) == {"study": 1_794_564_000_000}


def test_without_stands_no_card_is_complete_and_the_database_stays_quiet(fake_db):
    calls = fake_db(rows=[(99,)])
    assert repo.complete_cards([]) == 0
    assert calls == []


def test_complete_cards_counts_visitors_with_every_current_stand(fake_db):
    calls = fake_db(rows=[(6,)])
    assert repo.complete_cards(["a", "b", "c"]) == 6
    _, sql, params = calls[0]
    assert "HAVING COUNT(DISTINCT station_id) = %s" in sql
    assert params == (["a", "b", "c"], 3)


def test_visits_are_counted_per_stand(fake_db):
    fake_db(rows=[("a", 3), ("b", 1)])
    assert repo.visits_by_station() == {"a": 3, "b": 1}


def test_resetting_a_visitor_deletes_only_its_stamps_and_commits(fake_db):
    calls = fake_db()
    repo.delete_stamps_for(HASH)
    (_, sql, params), commit = calls
    assert sql == "DELETE FROM event_stamps WHERE visitor_hash = %s"
    assert params == (HASH,)
    assert commit == ("commit", None, None)


def test_resetting_everything_deletes_every_stamp_and_commits(fake_db):
    calls = fake_db()
    repo.delete_all_stamps()
    (_, sql, params), commit = calls
    assert sql == "DELETE FROM event_stamps"
    assert params is None
    assert commit == ("commit", None, None)


# --- wrong codes ----------------------------------------------------------------

def test_a_fresh_visitor_has_every_try_left_and_no_lock(fake_redis):
    assert repo.lock_state(HASH, JETZT) == (None, EVENT_CODE_MAX_ATTEMPTS)


def test_four_wrong_codes_count_down_without_a_lock(fake_redis):
    for erwartet in range(EVENT_CODE_MAX_ATTEMPTS - 1, 0, -1):
        assert repo.register_failure(HASH, JETZT) == (None, erwartet)
    assert repo.lock_state(HASH, JETZT) == (None, 1)


def test_the_fifth_wrong_code_locks_for_thirty_seconds_and_resets_the_counter(fake_redis):
    for _ in range(EVENT_CODE_MAX_ATTEMPTS - 1):
        repo.register_failure(HASH, JETZT)
    bis, versuche = repo.register_failure(HASH, JETZT)
    assert bis == JETZT + EVENT_CODE_LOCK_SECONDS * 1000
    assert versuche == EVENT_CODE_MAX_ATTEMPTS
    assert repo._count_key(HASH) not in fake_redis
    assert repo.lock_state(HASH, JETZT + 1000) == (bis, EVENT_CODE_MAX_ATTEMPTS)


def test_an_expired_lock_is_no_lock(fake_redis):
    fake_redis[repo._lock_key(HASH)] = JETZT - 1
    assert repo.lock_state(HASH, JETZT) == (None, EVENT_CODE_MAX_ATTEMPTS)


def test_without_redis_there_is_no_lock_and_every_try_counts_as_the_first(broken_redis):
    """The stands keep working when Redis is down, nobody gets locked out."""
    assert repo.lock_state(HASH, JETZT) == (None, EVENT_CODE_MAX_ATTEMPTS)
    assert repo.register_failure(HASH, JETZT) == (None, EVENT_CODE_MAX_ATTEMPTS)


def test_clearing_the_failures_drops_counter_and_lock(fake_redis):
    repo.register_failure(HASH, JETZT)
    fake_redis[repo._lock_key(HASH)] = JETZT + 10_000
    repo.clear_failures(HASH)
    assert fake_redis == {}


def test_clearing_the_failures_without_redis_is_quiet(broken_redis):
    repo.clear_failures(HASH)
