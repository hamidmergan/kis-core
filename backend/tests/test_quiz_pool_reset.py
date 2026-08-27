"""The one-off step that clears the quiz pool, with write-back and marker."""

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


def test_erst_zurueckschreiben_dann_loeschen():
    cur = _FakeCursor([None])
    assert schema._reset_quiz_pool_once(cur) is True
    anweisungen = [sql for sql, _ in cur.calls]
    update = next(i for i, s in enumerate(anweisungen)
                  if s.startswith("UPDATE aia_exercise_items"))
    delete = next(i for i, s in enumerate(anweisungen)
                  if s.startswith("DELETE FROM aia_exercise_pool"))
    assert update < delete
    assert "p.tool = 'quiz'" in anweisungen[update]
    assert "tool = 'quiz'" in anweisungen[delete]
    # Every content field has to go back, otherwise the exercise is left without options.
    for feld in ("back", "options", "correct_idx", "sources", "extras"):
        assert f"{feld} = p.{feld}" in anweisungen[update]


def test_der_schluessel_wird_danach_gesetzt():
    cur = _FakeCursor([None])
    schema._reset_quiz_pool_once(cur)
    letzte_sql, letzte_params = cur.calls[-1]
    assert letzte_sql.startswith("INSERT INTO settings")
    assert letzte_params == (schema._QUIZ_POOL_RESET_KEY,)


def test_mit_gesetztem_schluessel_passiert_nichts():
    """Otherwise every backend restart would lose the whole quiz pool."""
    cur = _FakeCursor([("true",)])
    assert schema._reset_quiz_pool_once(cur) is False
    anweisungen = [sql for sql, _ in cur.calls]
    assert not any(s.startswith("DELETE") or s.startswith("UPDATE") for s in anweisungen)
