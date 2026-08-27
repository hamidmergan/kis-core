"""The mark really has to reach the database, otherwise nothing sweeps."""

import json

import pytest

from src.features.ai_assistant.repository import context_cursors as repo


class _FakeCursor:
    def __init__(self, row, calls):
        self._row = row
        self._calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self._calls.append(("execute", sql, params))

    def fetchone(self):
        return self._row


class _FakeConn:
    def __init__(self, row, calls):
        self._row = row
        self._calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self, **kwargs):
        return _FakeCursor(self._row, self._calls)

    def commit(self):
        self._calls.append(("commit", None, None))


@pytest.fixture
def fake_db(monkeypatch):
    def _apply(row=None):
        calls: list[tuple] = []
        monkeypatch.setattr(repo, "get_connection", lambda: _FakeConn(row, calls))
        return calls
    return _apply


def test_writing_the_position_commits(fake_db):
    calls = fake_db()
    repo.set_context_cursors(3, 9, "karteikarten", [1, 2, 3])
    assert [c[0] for c in calls] == ["execute", "commit"], "the write must be committed"


def test_the_position_is_stored_as_json(fake_db):
    calls = fake_db()
    repo.set_context_cursors(3, 9, "karteikarten", [4, 5])
    _, _, params = calls[0]
    assert params[:3] == (3, 9, "karteikarten")
    assert json.loads(params[3]) == [4, 5]


def test_reading_a_row_that_is_not_there_is_a_first_run(fake_db):
    fake_db(row=None)
    assert repo.get_context_cursors(3, 9, "quiz") == []


def test_reading_a_stored_position(fake_db):
    fake_db(row=([1, 2, 3],))
    assert repo.get_context_cursors(3, 9, "quiz") == [1, 2, 3]


def test_a_position_handed_back_as_text_is_still_read(fake_db):
    # Older psycopg2 setups return JSONB as a string rather than as a list.
    fake_db(row=("[7, 8]",))
    assert repo.get_context_cursors(3, 9, "quiz") == [7, 8]


def test_an_unreadable_position_is_a_first_run_not_a_crash(fake_db):
    fake_db(row=("not json at all",))
    assert repo.get_context_cursors(3, 9, "quiz") == []
    fake_db(row=({"nope": 1},))
    assert repo.get_context_cursors(3, 9, "quiz") == []
