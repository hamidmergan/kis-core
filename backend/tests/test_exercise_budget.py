"""The exercise tools size their context from the number of items, the field is only the ceiling."""

import pytest

from src.features.ai_assistant.tasks import _context_budget as cb


def _chunks(source_id: int, pages: int, chars: int) -> list[dict]:
    return [{"page_number": p, "content": "x" * chars, "source_id": source_id}
            for p in range(1, pages + 1)]


def _picked_chars(picked) -> int:
    return sum(len(c["content"]) for _sid, _label, chunks in picked for c in chunks)


@pytest.fixture
def hohe_decke(monkeypatch):
    """The one remaining field, high enough that the number of exercises decides."""
    monkeypatch.setattr(cb, "tool_context_budget", lambda: 500000)
    monkeypatch.setattr("src.database.get_context_cursors", lambda w, s, t: [])
    monkeypatch.setattr("src.database.set_context_cursors", lambda w, s, t, c: None)
    monkeypatch.setattr("src.database.get_context_rotation", lambda w, t: None)
    monkeypatch.setattr("src.database.set_context_rotation", lambda w, t, s: None)


def test_the_budget_follows_the_number_of_exercises(hohe_decke):
    # A set of 15 reads 30k in its one call, a third of that for five.
    assert cb.exercise_context_budget(15) == 15 * 2000
    assert cb.exercise_context_budget(5) == 5 * 2000


def test_a_smaller_set_asks_for_less_material(hohe_decke):
    assert cb.exercise_context_budget(5) < cb.exercise_context_budget(15)


def test_the_field_is_the_ceiling_the_count_cannot_pass(monkeypatch):
    monkeypatch.setattr(cb, "tool_context_budget", lambda: 20000)
    assert cb.exercise_context_budget(15) == 20000


def test_the_exercise_tools_have_no_setting_of_their_own(monkeypatch):
    gelesen = []

    def get_setting(key, default):
        gelesen.append(key)
        return default

    monkeypatch.setattr("src.database.get_setting", get_setting)
    monkeypatch.setattr("src.services.model_limits.profile_for_feature", lambda feature="chat": None)
    cb.exercise_context_budget(15)
    assert gelesen == ["aia_tool_context_max_chars"]


def test_the_greedy_filler_asks_for_what_the_set_needs(hohe_decke):
    # A source far bigger than any budget, so the number of exercises alone decides.
    quellen = [(1, "q1.pdf", _chunks(1, 400, 500))]
    # The sweep takes one chunk per block whatever the budget, so five is the smallest set here.
    for count in (5, 15):
        budget = cb.exercise_context_budget(count)
        picked = _picked_chars(cb.fill_sources_greedy(quellen, 7, "quiz", count))
        assert budget * 0.9 <= picked <= budget, count


def test_the_even_filler_of_the_overview_tools_keeps_the_whole_field(monkeypatch):
    monkeypatch.setattr(cb, "tool_context_budget", lambda: 50000)
    quellen = [(1, "q1.pdf", _chunks(1, 100, 500))]
    picked = cb.fill_sources_evenly(quellen)
    # One separator per chunk is part of the budget, so the last chunk stays out.
    assert 45000 <= _picked_chars(picked) <= 50000


def test_the_even_filler_takes_a_budget_of_its_own(monkeypatch):
    monkeypatch.setattr(cb, "tool_context_budget", lambda: 50000)
    quellen = [(1, "q1.pdf", _chunks(1, 100, 500))]
    picked = cb.fill_sources_evenly(quellen, 10000)
    assert 9000 <= _picked_chars(picked) <= 10000


def test_the_overview_budget_is_capped_below_the_field(monkeypatch):
    # A mind map or a table reads at most 60k in its one call, the field only lowers that.
    monkeypatch.setattr(cb, "tool_context_budget", lambda: 500000)
    assert cb.overview_context_budget() == 60000
    monkeypatch.setattr(cb, "tool_context_budget", lambda: 20000)
    assert cb.overview_context_budget() == 20000


def test_the_answer_budget_grows_with_the_count():
    assert cb.exercise_max_tokens(1) == 600 + 400
    assert cb.exercise_max_tokens(15) == 600 + 15 * 400
    assert cb.exercise_max_tokens(0) == cb.exercise_max_tokens(1)
