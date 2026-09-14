"""The exercise tools read their own budget, the overview tools keep the tool budget."""

import pytest

from src.features.ai_assistant.tasks import _context_budget as cb


def _chunks(source_id: int, pages: int, chars: int) -> list[dict]:
    return [{"page_number": p, "content": "x" * chars, "source_id": source_id}
            for p in range(1, pages + 1)]


def _picked_chars(picked) -> int:
    return sum(len(c["content"]) for _sid, _label, chunks in picked for c in chunks)


@pytest.fixture
def zwei_budgets(monkeypatch):
    """Two clearly different budgets, so a mix-up shows up in the picked size."""
    monkeypatch.setattr(cb, "tool_context_budget", lambda tool="": 50000)
    monkeypatch.setattr(cb, "exercise_context_budget", lambda: 10000)
    monkeypatch.setattr("src.database.get_context_cursors", lambda w, s, t: [])
    monkeypatch.setattr("src.database.set_context_cursors", lambda w, s, t, c: None)
    monkeypatch.setattr("src.database.get_context_rotation", lambda w, t: None)
    monkeypatch.setattr("src.database.set_context_rotation", lambda w, t, s: None)


def test_the_exercise_budget_has_its_own_setting_and_default(monkeypatch):
    seen = {}

    def get_setting(key, default):
        seen["key"] = key
        return default

    monkeypatch.setattr("src.database.get_setting", get_setting)
    assert cb.exercise_context_budget() == 100000
    assert seen["key"] == "aia_exercise_context_max_chars"


def test_the_exercise_budget_is_capped_like_the_tool_budget(monkeypatch):
    monkeypatch.setattr("src.database.get_setting", lambda key, default: "5000000")
    assert cb.exercise_context_budget() == cb.tool_context_budget()


def test_the_greedy_filler_of_the_exercise_tools_uses_the_exercise_budget(zwei_budgets):
    # Twelve blocks each bring their first chunk, so the chunks stay small.
    quellen = [(1, "q1.pdf", _chunks(1, 100, 500))]
    picked = cb.fill_sources_greedy(quellen, 7, "quiz")
    assert 6000 <= _picked_chars(picked) <= 10000


def test_the_even_filler_of_the_overview_tools_keeps_the_tool_budget(zwei_budgets):
    quellen = [(1, "q1.pdf", _chunks(1, 100, 500))]
    picked = cb.fill_sources_evenly(quellen)
    # One separator per chunk is part of the budget, so the last chunk stays out.
    assert 45000 <= _picked_chars(picked) <= 50000
