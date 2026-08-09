"""Reading and writing the sweep position.

The position is a convenience, never a precondition: a set that generates from a repeated
window is worth more than a set that fails because a cursor could not be read.
"""

from src.features.ai_assistant.tasks._context_budget import read_cursors, write_cursors


def test_no_workspace_means_a_first_run():
    # Older queued tasks carry no workspace. They sweep from the start every time, which
    # is the behaviour before cursors existed.
    assert read_cursors(None, 5, "flashcards") == []


def test_reads_for_this_workspace_source_and_tool(monkeypatch):
    seen = {}

    def fake(workspace_id, source_id, tool):
        seen["args"] = (workspace_id, source_id, tool)
        return [1, 2, 3]

    monkeypatch.setattr("src.database.get_context_cursors", fake)
    assert read_cursors(7, 5, "quiz") == [1, 2, 3]
    assert seen["args"] == (7, 5, "quiz")


def test_a_failing_read_degrades_to_a_first_run(monkeypatch):
    def boom(*_args):
        raise RuntimeError("database is having a day")

    monkeypatch.setattr("src.database.get_context_cursors", boom)
    assert read_cursors(7, 5, "quiz") == []


def test_a_failing_write_does_not_reach_the_caller(monkeypatch):
    def boom(*_args):
        raise RuntimeError("database is having a day")

    monkeypatch.setattr("src.database.set_context_cursors", boom)
    write_cursors(7, 5, "quiz", [1, 2, 3])  # must not raise


def test_nothing_is_written_for_a_source_that_fitted_whole(monkeypatch):
    # An empty cursor list is what the selector returns when the whole source went in.
    # There is no position to keep, and writing one would be a lie about what was read.
    calls = []
    monkeypatch.setattr("src.database.set_context_cursors",
                        lambda *a: calls.append(a))
    write_cursors(7, 5, "quiz", [])
    assert calls == []


def test_nothing_is_written_without_a_workspace(monkeypatch):
    calls = []
    monkeypatch.setattr("src.database.set_context_cursors",
                        lambda *a: calls.append(a))
    write_cursors(None, 5, "quiz", [1, 2])
    assert calls == []


def test_writes_what_the_sweep_returned(monkeypatch):
    calls = []
    monkeypatch.setattr("src.database.set_context_cursors",
                        lambda *a: calls.append(a))
    write_cursors(7, 5, "quiz", [4, 5, 6])
    assert calls == [(7, 5, "quiz", [4, 5, 6])]
