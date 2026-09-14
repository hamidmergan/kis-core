"""Even context filling: every source gets a share and nothing is remembered."""

import pytest

from src.features.ai_assistant.tasks import _context_budget as cb


def _chunks(source_id: int, pages: int, chars: int) -> list[dict]:
    return [{"page_number": p, "content": "x" * chars, "source_id": source_id}
            for p in range(1, pages + 1)]


def _sources(*sizes: tuple[int, int]) -> list[tuple[int, str, list[dict]]]:
    """One entry per source: ``(pages, chars per page)`` becomes id, label, chunks."""
    return [(i, f"q{i}.pdf", _chunks(i, pages, chars))
            for i, (pages, chars) in enumerate(sizes, start=1)]


def _labels(picked) -> list[str]:
    return [label for _sid, label, _chunks in picked]


@pytest.fixture
def budget(monkeypatch):
    """The tool budget under test control."""
    state = {"budget": 100000}
    monkeypatch.setattr(cb, "tool_context_budget", lambda tool="": state["budget"])
    return state


def test_every_source_is_represented_when_the_budget_is_tight(budget):
    # Greedy filling would spend everything on q1 and drop the other two.
    budget["budget"] = 30000
    picked = cb.fill_sources_evenly(_sources((60, 500), (60, 500), (60, 500)))
    assert _labels(picked) == ["q1.pdf", "q2.pdf", "q3.pdf"]


def test_a_small_source_hands_its_rest_to_the_others(budget):
    # A blind third would be 10000 characters, about 20 chunks.
    budget["budget"] = 30000
    picked = cb.fill_sources_evenly(_sources((60, 500), (60, 500), (2, 500)))
    gross = [len(chunks) for _sid, label, chunks in picked if label != "q3.pdf"]
    assert all(n > 20 for n in gross)


def test_the_result_keeps_the_selection_order(budget):
    # Filling starts at the smallest source, the answer must not.
    budget["budget"] = 30000
    picked = cb.fill_sources_evenly(_sources((60, 500), (60, 500), (2, 500)))
    assert _labels(picked) == ["q1.pdf", "q2.pdf", "q3.pdf"]


def test_a_share_sweeps_the_whole_source_not_only_its_front(budget):
    budget["budget"] = 6000
    picked = cb.fill_sources_evenly(_sources((200, 100),))
    seiten = [c["page_number"] for c in picked[0][2]]
    assert min(seiten) < 40 and max(seiten) > 150


def test_the_first_page_is_always_part_of_the_share(budget):
    budget["budget"] = 6000
    picked = cb.fill_sources_evenly(_sources((200, 100),))
    assert picked[0][2][0]["page_number"] == 1


def test_two_runs_read_exactly_the_same_material(budget):
    budget["budget"] = 6000
    quellen = _sources((200, 100),)
    erster = cb.fill_sources_evenly(quellen)
    zweiter = cb.fill_sources_evenly(quellen)
    assert ([c["page_number"] for c in erster[0][2]]
            == [c["page_number"] for c in zweiter[0][2]])


def test_no_mark_is_written(budget, monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("the even fill must not remember anything")

    monkeypatch.setattr("src.database.set_context_cursors", boom)
    monkeypatch.setattr("src.database.set_context_rotation", boom)
    budget["budget"] = 6000
    cb.fill_sources_evenly(_sources((200, 100),))


def test_an_empty_source_costs_nothing(budget):
    budget["budget"] = 6000
    quellen = [(1, "leer.pdf", []), (2, "voll.pdf", _chunks(2, 50, 100))]
    picked = cb.fill_sources_evenly(quellen)
    assert _labels(picked) == ["voll.pdf"]


def test_without_any_source_nothing_comes_back(budget):
    assert cb.fill_sources_evenly([]) == []
