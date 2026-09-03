"""The one-off step that clears every level once, because the trainer moved to the person."""

from src.core.db import schema


class _FakeCursor:
    def __init__(self, rows):
        self._rows = list(rows)
        self.calls = []

    def execute(self, sql, params=None):
        # Untruncated, otherwise the test would silently pass.
        self.calls.append((" ".join(sql.split()), params))

    def fetchone(self):
        return self._rows.pop(0) if self._rows else None


def test_levels_are_cleared_once():
    cur = _FakeCursor([None])
    assert schema._reset_language_training_once(cur) is True
    anweisungen = [sql for sql, _ in cur.calls]
    update = next(s for s in anweisungen if s.startswith("UPDATE users"))
    assert "language_level = NULL" in update
    assert "language_level_set_at = NULL" in update
    assert "WHERE" not in update


def test_the_key_is_set_afterwards():
    cur = _FakeCursor([None])
    schema._reset_language_training_once(cur)
    letzte_sql, letzte_params = cur.calls[-1]
    assert letzte_sql.startswith("INSERT INTO settings")
    assert letzte_params == (schema._LANGUAGE_TRAINING_RESET_KEY,)


def test_with_the_key_set_nothing_happens():
    """Otherwise every backend restart would wipe every level again."""
    cur = _FakeCursor([("true",)])
    assert schema._reset_language_training_once(cur) is False
    assert not any(sql.startswith("UPDATE") for sql, _ in cur.calls)
