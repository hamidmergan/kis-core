"""One admin field, one share per overview tool."""

import pytest

from src.features.ai_assistant.tasks import _context_budget as cb


@pytest.fixture
def feld(monkeypatch):
    """The admin field under test control."""
    state = {"wert": 500000}
    monkeypatch.setattr("src.database.get_setting", lambda key, default: str(state["wert"]))
    return state


def test_the_mindmap_gets_the_whole_field(feld):
    assert cb.tool_context_budget("mindmap") == 500000


def test_the_schedule_and_the_table_get_four_fifths(feld):
    assert cb.tool_context_budget("schedule") == 400000
    assert cb.tool_context_budget("data_table") == 400000


def test_the_podcast_gets_half(feld):
    assert cb.tool_context_budget("podcast") == 250000


def test_a_lower_field_moves_every_share_with_it(feld):
    feld["wert"] = 100000
    assert cb.tool_context_budget("mindmap") == 100000
    assert cb.tool_context_budget("schedule") == 80000
    assert cb.tool_context_budget("podcast") == 50000


def test_an_unnamed_tool_gets_the_whole_field(feld):
    assert cb.tool_context_budget() == 500000


def test_the_table_fills_less_than_the_mindmap_from_the_same_material(feld):
    # Same sources, same field: only the share may make the difference.
    quellen = [(1, "q1.pdf", [{"page_number": p, "content": "x" * 1000} for p in range(1, 900)])]
    mindmap = cb.fill_sources_evenly(quellen, "mindmap")
    tabelle = cb.fill_sources_evenly(quellen, "data_table")
    assert len(tabelle[0][2]) < len(mindmap[0][2])
