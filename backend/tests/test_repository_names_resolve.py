"""Two repository functions called a helper their module never imported."""

from src.features.admin.repository import users
from src.features.ai_assistant.repository import enrollments


class _Cursor:
    def __init__(self, calls):
        self._calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self._calls.append((" ".join(sql.split()), params))

    def fetchone(self):
        return {"total": 0}

    def fetchall(self):
        return []


class _Conn:
    def __init__(self, calls):
        self._calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self, **kwargs):
        return _Cursor(self._calls)


def test_user_list_filters_by_date(monkeypatch):
    calls: list[tuple] = []
    monkeypatch.setattr(users, "get_connection", lambda: _Conn(calls))
    rows, _total = users.get_all_users(date_from="2026-09-01", date_to="2026-09-30")
    assert rows == []
    params = [p for _sql, p in calls if p][0]
    assert params[:2] == ["2026-08-31 22:00:00", "2026-09-30 21:59:59"]


def test_unknown_enroll_code_falls_back_to_the_workspace_table(monkeypatch):
    calls: list[tuple] = []
    monkeypatch.setattr(enrollments, "get_workspace_by_access_link_code", lambda code: None)
    monkeypatch.setattr(enrollments, "get_connection", lambda: _Conn(calls))
    assert enrollments.get_workspace_by_enroll_code("ABC123") == {"total": 0}
    assert "aia_workspaces" in calls[0][0]


def test_enroll_code_of_a_link_returns_its_workspace(monkeypatch):
    monkeypatch.setattr(
        enrollments, "get_workspace_by_access_link_code", lambda code: ({"id": 7}, {"id": 1}))
    assert enrollments.get_workspace_by_enroll_code("ABC123") == {"id": 7}
