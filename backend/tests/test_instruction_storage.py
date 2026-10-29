"""The instruction is stored on the row, the marker written, the length checked."""

import pytest
from pydantic import ValidationError

from src.features.ai_assistant import schemas
from src.features.ai_assistant.repository import data_tables, exercises, instructions, mindmaps
from src.limits import AIA_INSTRUCTION_MAX_CHARS


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


def _fake(monkeypatch, modul, rows=()):
    calls: list[tuple] = []
    monkeypatch.setattr(modul, "get_connection", lambda: _FakeConn(rows, calls))
    return calls


def _sql(calls):
    return [c[1] for c in calls if c[0] == "execute"]


# --- the row carries the instruction -------------------------------------------

def test_the_mindmap_row_stores_the_instruction(monkeypatch):
    calls = _fake(monkeypatch, mindmaps, rows=[(4,)])
    assert mindmaps.create_aia_mindmap(7, 1, [1, 2], user_instruction="nur Kapitel 3") == 4
    assert "user_instruction" in _sql(calls)[0]
    assert "nur Kapitel 3" in calls[0][2]


def test_the_mindmap_row_stores_null_without_an_instruction(monkeypatch):
    calls = _fake(monkeypatch, mindmaps, rows=[(4,)])
    mindmaps.create_aia_mindmap(7, 1, [1])
    assert None in calls[0][2]


def test_the_table_row_stores_the_instruction(monkeypatch):
    calls = _fake(monkeypatch, data_tables, rows=[(4,)])
    assert data_tables.create_aia_data_table(7, 1, [1], user_instruction="nur Fristen") == 4
    assert "user_instruction" in _sql(calls)[0]
    assert "nur Fristen" in calls[0][2]


def test_the_set_placeholder_stores_the_instruction(monkeypatch):
    calls = _fake(monkeypatch, exercises, rows=[{"id": 9}])
    exercises.create_exercise_set_placeholder(
        7, 1, "quiz", "Wird generiert…", "source", "u1", source_uuids=["u1"],
        requested_count=5, user_instruction="leichte Fragen")
    assert "user_instruction" in _sql(calls)[0]
    assert "leichte Fragen" in calls[0][2]


# --- the marker ------------------------------------------------------------------

@pytest.mark.parametrize("table", ["aia_mindmaps", "aia_data_tables", "aia_exercise_sets"])
@pytest.mark.parametrize("unmatched", [True, False])
def test_the_flag_is_written_with_its_value_and_committed(monkeypatch, table, unmatched):
    calls = _fake(monkeypatch, instructions)
    instructions.set_instruction_unmatched(table, 5, unmatched)
    assert _sql(calls) == [f"UPDATE {table} SET instruction_unmatched = %s WHERE id = %s"]
    assert calls[0][2] == (unmatched, 5)
    assert calls[-1][0] == "commit"


def test_an_unknown_table_is_refused(monkeypatch):
    calls = _fake(monkeypatch, instructions)
    with pytest.raises(ValueError):
        instructions.set_instruction_unmatched("users", 5, True)
    assert calls == []


# --- the length in the schema --------------------------------------------------------

@pytest.mark.parametrize("body", [
    lambda text: schemas.MindmapGenerateBody(active_source_ids=["u1"], instruction=text),
    lambda text: schemas.DataTableGenerateBody(active_source_ids=["u1"], instruction=text),
    lambda text: schemas.CreateSetBody(tool="quiz", instruction=text),
])
def test_the_instruction_is_optional_and_capped(body):
    assert body("nur Kapitel 3").instruction == "nur Kapitel 3"
    assert body("x" * AIA_INSTRUCTION_MAX_CHARS).instruction
    with pytest.raises(ValidationError):
        body("x" * (AIA_INSTRUCTION_MAX_CHARS + 1))


def test_the_instruction_defaults_to_empty():
    assert schemas.MindmapGenerateBody(active_source_ids=["u1"]).instruction == ""
    assert schemas.DataTableGenerateBody(active_source_ids=["u1"]).instruction == ""
    assert schemas.CreateSetBody(tool="quiz").instruction == ""
