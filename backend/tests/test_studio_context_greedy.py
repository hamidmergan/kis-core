"""Mindmap and data table collect their material greedily, with their own marks."""

import pytest

from src.features.ai_assistant.tasks.studio import data_table, mindmap


def _chunks(source_id: int, pages: int, chars: int) -> list[dict]:
    return [{"page_number": p, "content": "x" * chars, "source_id": source_id}
            for p in range(1, pages + 1)]


@pytest.fixture
def welt(monkeypatch):
    """Three equal sources in one module, budget and marks under test control."""
    state = {"budget": 100000, "rotation": {}}
    quellen = {f"u{i}": {"id": i, "filename": f"q{i}.pdf", "workspace_id": 7}
               for i in (1, 2, 3)}

    monkeypatch.setattr("src.database.get_aia_source", lambda u: quellen.get(u))
    monkeypatch.setattr("src.database.get_chunks_by_source", lambda sid: _chunks(sid, 60, 500))
    monkeypatch.setattr("src.database.get_context_cursors", lambda w, s, t: [])
    monkeypatch.setattr("src.database.set_context_cursors", lambda w, s, t, c: None)
    monkeypatch.setattr("src.database.get_context_rotation",
                        lambda w, t: state["rotation"].get((w, t)))
    monkeypatch.setattr("src.database.set_context_rotation",
                        lambda w, t, s: state["rotation"].__setitem__((w, t), s))
    monkeypatch.setattr(
        "src.features.ai_assistant.tasks._context_budget.tool_context_budget",
        lambda: state["budget"])
    return state


_IDS = [1, 2, 3]
_UUIDS = ["u1", "u2", "u3"]
_MAP = {"1": {"filename": "q1.pdf"}, "2": {"filename": "q2.pdf"}, "3": {"filename": "q3.pdf"}}


# --- mindmap -----------------------------------------------------------------

def test_the_mindmap_takes_every_source_that_fits(welt):
    gesammelt = mindmap._collect_sources(_IDS, _UUIDS)
    assert [label for _sid, label, _all, _picked in gesammelt] == ["q1.pdf", "q2.pdf", "q3.pdf"]


def test_the_mindmap_drops_the_tail_when_the_budget_is_full(welt):
    welt["budget"] = 32000
    gesammelt = mindmap._collect_sources(_IDS, _UUIDS)
    assert [label for _sid, label, _all, _picked in gesammelt] == ["q1.pdf"]


def test_the_mindmap_keeps_all_chunks_for_the_timestamps(welt):
    # The picked window shrinks, the full list has to stay for media citations.
    welt["budget"] = 20000
    _sid, _label, alle, picked = mindmap._collect_sources(_IDS, _UUIDS)[0]
    assert len(alle) == 60
    assert len(picked) < 60


def test_the_mindmap_now_carries_its_own_mark(welt):
    welt["budget"] = 32000
    mindmap._collect_sources(_IDS, _UUIDS)
    assert welt["rotation"][(7, "mindmap")] == 2


# --- data table --------------------------------------------------------------

def test_the_table_drops_the_tail_when_the_budget_is_full(welt):
    welt["budget"] = 32000
    gesammelt = data_table._collect_sources(_IDS, _UUIDS, _MAP)
    assert [label for _sid, label, _picked in gesammelt] == ["q1.pdf"]


def test_the_table_rotates_apart_from_the_mindmap(welt):
    welt["budget"] = 32000
    mindmap._collect_sources(_IDS, _UUIDS)
    gesammelt = data_table._collect_sources(_IDS, _UUIDS, _MAP)
    assert [label for _sid, label, _picked in gesammelt] == ["q1.pdf"]
    assert welt["rotation"][(7, "datatable")] == 2
