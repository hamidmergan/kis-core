"""Checks that finalizing a set permanently marks its pool exercises as seen."""

import pytest

from src.features.ai_assistant.repository import exercises as repo


class _FakeCursor:
    def __init__(self, calls):
        self._calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self._calls.append(("execute", " ".join(sql.split()), params))

    def fetchone(self):
        return {"id": 1}


class _FakeConn:
    def __init__(self, calls):
        self._calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self, **kwargs):
        return _FakeCursor(self._calls)

    def commit(self):
        self._calls.append(("commit", None, None))


@pytest.fixture
def fake_db(monkeypatch):
    calls: list[tuple] = []
    monkeypatch.setattr(repo, "get_connection", lambda: _FakeConn(calls))
    return calls


def _pool_item(front="a", pool_item_id=100):
    return {"front": front, "back": "", "pool_item_id": pool_item_id}


def _fresh_item(front="a"):
    return {"front": front, "back": "A"}


def test_a_pool_item_is_marked_seen_for_the_user(fake_db):
    repo.finalize_exercise_set(1, "T", [_pool_item()], user_id=7)
    marker = [c for c in fake_db if c[0] == "execute" and "aia_exercise_pool_seen" in c[1]]
    assert len(marker) == 1
    assert marker[0][2] == (100, 7)


def test_an_item_without_a_pool_reference_is_not_marked(fake_db):
    """Glossary-sourced exercises never enter the pool, there is nothing to mark."""
    repo.finalize_exercise_set(1, "T", [_fresh_item()], user_id=7)
    assert not any("aia_exercise_pool_seen" in c[1] for c in fake_db if c[0] == "execute")


def test_without_a_user_id_nothing_is_marked(fake_db):
    """A caller that does not pass a user must not crash or write a row."""
    repo.finalize_exercise_set(1, "T", [_pool_item()])
    assert not any("aia_exercise_pool_seen" in c[1] for c in fake_db if c[0] == "execute")


def test_every_pool_item_of_the_set_is_marked(fake_db):
    repo.finalize_exercise_set(
        1, "T", [_pool_item("a", 100), _pool_item("b", 101)], user_id=7)
    marker = [c for c in fake_db if c[0] == "execute" and "aia_exercise_pool_seen" in c[1]]
    assert {c[2] for c in marker} == {(100, 7), (101, 7)}


def test_the_saved_items_are_unaffected(fake_db):
    repo.finalize_exercise_set(1, "T", [_pool_item("a", 100)], user_id=7)
    inserts = [c for c in fake_db if c[0] == "execute"
               and c[1].startswith("INSERT INTO aia_exercise_items")]
    assert len(inserts) == 1
