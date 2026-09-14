"""Greedy context filling: each source takes what is left, the rest falls away."""

import pytest

from src.features.ai_assistant.tasks import _context_budget as cb


def _chunks(source_id: int, pages: int, chars: int) -> list[dict]:
    return [{"page_number": p, "content": "x" * chars, "source_id": source_id}
            for p in range(1, pages + 1)]


@pytest.fixture
def welt(monkeypatch):
    """A fake module: budget, per-source marks and the rotation mark live in dicts."""
    state = {"budget": 100000, "cursors": {}, "rotation": {}}

    monkeypatch.setattr(cb, "exercise_context_budget", lambda: state["budget"])
    monkeypatch.setattr("src.database.get_context_cursors",
                        lambda w, s, t: state["cursors"].get((w, s, t), []))
    monkeypatch.setattr("src.database.set_context_cursors",
                        lambda w, s, t, c: state["cursors"].__setitem__((w, s, t), list(c)))
    monkeypatch.setattr("src.database.get_context_rotation",
                        lambda w, t: state["rotation"].get((w, t)))
    monkeypatch.setattr("src.database.set_context_rotation",
                        lambda w, t, s: state["rotation"].__setitem__((w, t), s))
    return state


def _labels(picked) -> list[str]:
    return [label for _sid, label, _chunks in picked]


def _sources(*sizes: tuple[int, int]) -> list[tuple[int, str, list[dict]]]:
    """One entry per source: ``(pages, chars per page)`` becomes id, label, chunks."""
    return [(i, f"q{i}.pdf", _chunks(i, pages, chars))
            for i, (pages, chars) in enumerate(sizes, start=1)]


# --- filling -----------------------------------------------------------------

def test_everything_that_fits_comes_along(welt):
    welt["budget"] = 100000
    picked = cb.fill_sources_greedy(_sources((10, 100), (10, 100), (10, 100)), 1, "flashcards")
    assert _labels(picked) == ["q1.pdf", "q2.pdf", "q3.pdf"]


def test_the_first_source_takes_what_it_needs_not_a_fair_share(welt):
    # Old behaviour split the budget in three, the first source would lose two thirds.
    welt["budget"] = 6000
    picked = cb.fill_sources_greedy(_sources((50, 100), (50, 100), (50, 100)), 1, "flashcards")
    erste = next(chunks for _sid, label, chunks in picked if label == "q1.pdf")
    assert len(erste) == 50


def test_the_tail_falls_away_when_the_budget_is_full(welt):
    welt["budget"] = 6000
    picked = cb.fill_sources_greedy(_sources((50, 100), (50, 100), (50, 100)), 1, "flashcards")
    assert _labels(picked) == ["q1.pdf"]


def test_a_source_too_big_for_the_budget_is_swept_not_cut(welt):
    # A single oversized source still has to cover its whole length.
    welt["budget"] = 3000
    picked = cb.fill_sources_greedy(_sources((200, 100),), 1, "flashcards")
    seiten = [c["page_number"] for c in picked[0][2]]
    assert min(seiten) < 40 and max(seiten) > 150


def test_an_empty_source_costs_nothing(welt):
    welt["budget"] = 6000
    quellen = [(1, "leer.pdf", []), *_sources((50, 100))]
    quellen[1] = (2, "voll.pdf", _chunks(2, 50, 100))
    picked = cb.fill_sources_greedy(quellen, 1, "flashcards")
    assert _labels(picked) == ["voll.pdf"]


def test_the_result_keeps_the_selection_order(welt):
    welt["budget"] = 100000
    welt["rotation"][(1, "flashcards")] = 3
    picked = cb.fill_sources_greedy(_sources((5, 100), (5, 100), (5, 100)), 1, "flashcards")
    assert _labels(picked) == ["q1.pdf", "q2.pdf", "q3.pdf"]


# --- the rotation mark -------------------------------------------------------

def test_the_next_run_starts_where_this_one_stopped(welt):
    welt["budget"] = 6000
    cb.fill_sources_greedy(_sources((50, 100), (50, 100), (50, 100)), 1, "flashcards")
    assert welt["rotation"][(1, "flashcards")] == 2


def test_the_next_run_really_reads_the_source_that_missed_out(welt):
    welt["budget"] = 6000
    quellen = _sources((50, 100), (50, 100), (50, 100))
    cb.fill_sources_greedy(quellen, 1, "flashcards")
    zweiter = cb.fill_sources_greedy(quellen, 1, "flashcards")
    assert _labels(zweiter) == ["q2.pdf"]


def test_the_mark_is_cleared_once_every_source_got_its_turn(welt):
    welt["budget"] = 100000
    cb.fill_sources_greedy(_sources((5, 100), (5, 100)), 1, "flashcards")
    assert welt["rotation"][(1, "flashcards")] is None


def test_a_stale_mark_starts_at_the_front_again(welt):
    # The source it points at was deselected or deleted since the last run.
    welt["budget"] = 6000
    welt["rotation"][(1, "flashcards")] = 99
    picked = cb.fill_sources_greedy(_sources((50, 100), (50, 100)), 1, "flashcards")
    assert _labels(picked) == ["q1.pdf"]


def test_each_tool_rotates_on_its_own(welt):
    welt["budget"] = 6000
    quellen = _sources((50, 100), (50, 100))
    cb.fill_sources_greedy(quellen, 1, "flashcards")
    picked = cb.fill_sources_greedy(quellen, 1, "quiz")
    assert _labels(picked) == ["q1.pdf"]


# --- the per-document mark stays ---------------------------------------------

def test_the_per_document_mark_moves_on(welt):
    welt["budget"] = 3000
    quellen = _sources((200, 100),)
    erster = cb.fill_sources_greedy(quellen, 1, "flashcards")
    zweiter = cb.fill_sources_greedy(quellen, 1, "flashcards")
    assert [c["page_number"] for c in erster[0][2]] != [c["page_number"] for c in zweiter[0][2]]


def test_a_source_that_fits_whole_keeps_no_mark(welt):
    welt["budget"] = 100000
    cb.fill_sources_greedy(_sources((5, 100),), 1, "flashcards")
    assert (1, 1, "flashcards") not in welt["cursors"]


def test_without_a_module_nothing_is_remembered(welt):
    # A podcast-style call has no course room, it must still fill.
    welt["budget"] = 100000
    picked = cb.fill_sources_greedy(_sources((5, 100), (5, 100)), None, "flashcards")
    assert _labels(picked) == ["q1.pdf", "q2.pdf"]
    assert welt["rotation"] == {}
