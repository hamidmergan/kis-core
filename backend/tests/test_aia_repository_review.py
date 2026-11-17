"""Fixes from the line-by-line review of the learning assistant's repository."""

from datetime import datetime

import pytest

from src.features.ai_assistant.repository import chunks, exercises, schedule, stats

# NOW() is a timestamptz, this double conversion lands on the previous day after local midnight.
_WRONG_TODAY = "NOW() AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Berlin'"


class _Cursor:
    def __init__(self, calls, rows):
        self._calls = calls
        self._rows = rows
        self.rowcount = 1

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self._calls.append((" ".join(sql.split()), params))

    def fetchone(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return list(self._rows)


class _Conn:
    def __init__(self, calls, rows=()):
        self._calls = calls
        self._rows = rows

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self, **kwargs):
        return _Cursor(self._calls, self._rows)

    def commit(self):
        self._calls.append(("commit", None))


@pytest.fixture
def calls(monkeypatch):
    protokoll: list[tuple] = []
    for modul in (exercises, schedule, stats):
        monkeypatch.setattr(modul, "get_connection", lambda: _Conn(protokoll))
    return protokoll


def test_practised_today_compares_with_the_local_day(calls):
    exercises.hat_heute_geuebt(1, 2)
    sql = calls[0][0]
    assert _WRONG_TODAY not in sql
    assert "= (NOW() AT TIME ZONE 'Europe/Berlin')::date" in sql


def test_the_activity_feed_shows_a_renamed_mind_map(calls):
    stats.get_recent_activities(1, 2)
    assert "COALESCE(m.title, m.mindmap->>'topic', 'Mindmap')" in calls[0][0]


def test_student_stats_never_take_today_from_the_double_conversion(monkeypatch):
    protokoll: list[tuple] = []
    zeile = {"total": 0, "today": 0, "first_activity": None, "current_streak": 0,
             "max_streak": 0, "last_active_date": None}

    class _Stats(_Cursor):
        def fetchall(self):
            return []

    class _StatsConn(_Conn):
        def cursor(self, **kwargs):
            return _Stats(self._calls, [zeile])

    monkeypatch.setattr(stats, "get_connection", lambda: _StatsConn(protokoll))
    ergebnis = stats.get_student_stats(1, 2)
    assert len(ergebnis["heatmap"]) == stats.STATS_WINDOW_DAYS
    assert ergebnis["overview"]["total_sets"] == 0
    assert all(_WRONG_TODAY not in sql for sql, _p in protokoll)


def test_ticking_an_entry_stores_the_same_clock_for_both_kinds(calls):
    schedule.update_schedule_entry(1, 2, is_checked=True)
    schedule.update_personal_entry(1, 2, is_checked=True)
    zeiten = [p for _sql, p in calls if p for p in p if isinstance(p, datetime)]
    assert len(zeiten) == 2
    assert abs((zeiten[0] - zeiten[1]).total_seconds()) < 5


def test_a_partial_update_keeps_its_column_order_and_clears_with_null(calls):
    schedule.update_schedule_entry(7, 2, title="A", clear_date=True, due_time="10:00",
                                   date_precision="week", is_optional=False)
    sql, params = calls[0]
    assert "SET title = %s, due_date = NULL, due_time = %s, is_optional = %s, updated_at = NOW()" in sql
    assert params == ["A", "10:00", False, 7, 2]


def test_an_empty_workspace_is_not_remembered_as_empty(monkeypatch):
    monkeypatch.setattr(chunks, "_IDF_N_CACHE", {})
    monkeypatch.setattr(chunks, "_IDF_CACHE", {})
    anzahl = [0]

    class _Cur:
        def __init__(self):
            self._last = ""

        def execute(self, sql, params=None):
            self._last = sql

        def fetchone(self):
            return (anzahl[0],)

        def fetchall(self):
            return [{"w": "pruefung", "df": 2}]

    assert chunks._term_idf(_Cur(), 5, ["Pruefung"]) == []
    anzahl[0] = 10
    treffer = chunks._term_idf(_Cur(), 5, ["Pruefung"])
    assert [w for w, _idf in treffer] == ["Pruefung"]
