"""The database side of feedback entries: written, committed, correctly conditioned."""

import pytest

from src.features.feedback import repository as repo


class _FakeCursor:
    def __init__(self, rows, calls):
        self._rows = list(rows)
        self._calls = calls
        self.rowcount = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self._calls.append(("execute", " ".join(sql.split()), params))
        self.rowcount = 1

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


def test_creating_an_entry_commits(fake_db):
    calls = fake_db(rows=[(9,)])

    neu = repo.create_feedback(
        category="bug", message="Upload haengt", contact=None, username=None,
        page_path="/workspace/abc",
    )

    assert neu == 9
    anweisungen = [c for c in calls if c[0] == "execute"]
    assert len(anweisungen) == 1
    assert anweisungen[0][2] == ("bug", "Upload haengt", None, None, "/workspace/abc")
    assert ("commit", None, None) in calls


def test_creating_an_entry_can_carry_the_opted_in_username(fake_db):
    calls = fake_db(rows=[(9,)])
    repo.create_feedback(
        category="idea", message="Mehr Farben", contact=None, username="Hans Müller",
        page_path=None,
    )
    anweisungen = [c for c in calls if c[0] == "execute"]
    assert anweisungen[0][2] == ("idea", "Mehr Farben", None, "Hans Müller", None)


def test_adding_an_attachment_commits(fake_db):
    calls = fake_db(rows=[(4,)])
    neu = repo.add_attachment(
        feedback_id=9, filename="screen.png", content_type="image/png",
        size_bytes=1234, storage_key="feedback/9/abc.png",
    )
    assert neu == 4
    assert ("commit", None, None) in calls


def test_getting_an_unknown_attachment_returns_none(fake_db):
    fake_db(rows=[])
    assert repo.get_attachment(99) is None


def test_listing_shows_the_newest_first(fake_db):
    calls = fake_db(rows=[])
    assert repo.list_feedback() == []
    anweisungen = [c[1] for c in calls if c[0] == "execute"]
    assert any("ORDER BY created_at DESC" in a for a in anweisungen)


def test_listing_groups_attachments_under_their_entry(monkeypatch):
    calls: list[tuple] = []

    class _Cursor:
        def __init__(self, plan):
            self._plan = plan

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def execute(self, sql, params=None):
            calls.append(("execute", " ".join(sql.split()), params))

        def fetchall(self):
            return self._plan.pop(0)

    class _Conn:
        def __init__(self, plan):
            self._plan = plan

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def cursor(self, **kwargs):
            return _Cursor(self._plan)

    feedback_rows = [{"id": 1, "message": "x"}, {"id": 2, "message": "y"}]
    attachment_rows = [{"id": 10, "feedback_id": 1, "filename": "a.png"}]
    monkeypatch.setattr(repo, "get_connection", lambda: _Conn([feedback_rows, attachment_rows]))

    ergebnis = repo.list_feedback()

    assert ergebnis[0]["attachments"] == [{"id": 10, "feedback_id": 1, "filename": "a.png"}]
    assert ergebnis[1]["attachments"] == []


def test_setting_the_status_commits(fake_db):
    calls = fake_db(rows=[(3,)])
    assert repo.set_feedback_status(3, "done") is True
    assert ("commit", None, None) in calls


def test_marking_an_unknown_entry_reports_failure(fake_db):
    fake_db(rows=[])
    assert repo.set_feedback_status(99, "parked") is False


def test_deleting_removes_and_commits_then_clears_storage(fake_db, monkeypatch):
    calls = fake_db(rows=[(3,)])
    geloescht = []
    monkeypatch.setattr(repo.storage, "delete_feedback_attachments", lambda fid: geloescht.append(fid))

    assert repo.delete_feedback(3) is True

    anweisungen = [c[1] for c in calls if c[0] == "execute"]
    assert any("DELETE FROM feedback" in a for a in anweisungen)
    assert ("commit", None, None) in calls
    assert geloescht == [3]


def test_deleting_an_unknown_entry_reports_failure_and_touches_no_storage(fake_db, monkeypatch):
    fake_db(rows=[])
    geloescht = []
    monkeypatch.setattr(repo.storage, "delete_feedback_attachments", lambda fid: geloescht.append(fid))

    assert repo.delete_feedback(99) is False
    assert geloescht == []
