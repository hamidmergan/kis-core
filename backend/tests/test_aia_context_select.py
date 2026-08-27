"""Chunk selection for the context window, checked for coverage and progress."""

from src.features.ai_assistant.tasks._context_budget import (
    _COVERAGE_BLOCKS,
    select_chunks_for_budget,
)


def _chunks(n: int, size: int = 100) -> list[dict]:
    return [{"page_number": i + 1, "content": "x" * size} for i in range(n)]


def _pages(chunks: list[dict]) -> list[int]:
    return [c["page_number"] for c in chunks]


def test_returns_all_when_it_fits():
    cs = _chunks(10, 100)
    picked, cursors = select_chunks_for_budget(cs, 100000)
    assert picked == cs
    # Nothing was skipped, so there is no position to resume from.
    assert cursors == []


def test_empty_in_empty_out():
    picked, cursors = select_chunks_for_budget([], 1000)
    assert picked == []
    assert cursors == []


def test_oversized_is_trimmed_to_budget():
    cs = _chunks(100, 100)  # ~10100 chars
    picked, _ = select_chunks_for_budget(cs, 2000)
    total = sum(len(c["content"]) + 1 for c in picked)
    assert total <= 2000
    assert 0 < len(picked) < 100


def test_oversized_covers_whole_document_not_just_front():
    # One window per block, otherwise every exercise hangs on page 1.
    cs = _chunks(120, 100)
    picked, _ = select_chunks_for_budget(cs, 3000)
    pages = _pages(picked)
    assert max(pages) > 80  # something from the last third
    assert min(pages) < 40  # and the front


def test_first_run_starts_at_the_very_first_chunk():
    # A sweep starts at the beginning, unlike the old random selection.
    cs = _chunks(120, 100)
    picked, _ = select_chunks_for_budget(cs, 3000)
    assert min(_pages(picked)) == 1


def test_returned_in_document_order():
    cs = _chunks(120, 100)
    picked, _ = select_chunks_for_budget(cs, 3000)
    pages = _pages(picked)
    assert pages == sorted(pages)


def test_second_run_reads_other_material():
    cs = _chunks(200, 100)
    first, cursors = select_chunks_for_budget(cs, 3000)
    second, _ = select_chunks_for_budget(cs, 3000, cursors=cursors)
    assert _pages(first) != _pages(second)
    # And not merely shuffled: the two runs barely overlap.
    assert len(set(_pages(first)) & set(_pages(second))) == 0


def test_same_cursors_give_the_same_run():
    # No randomness anywhere, so a run can be reproduced from its stored cursors.
    cs = _chunks(200, 100)
    a, ca = select_chunks_for_budget(cs, 3000, cursors=[3] * _COVERAGE_BLOCKS)
    b, cb = select_chunks_for_budget(cs, 3000, cursors=[3] * _COVERAGE_BLOCKS)
    assert a == b
    assert ca == cb


def test_sweep_covers_every_chunk_in_close_to_the_fewest_runs():
    """The whole document gets read, roughly as fast as the budget allows."""
    cs = _chunks(200, 100)
    total = sum(len(c["content"]) + 1 for c in cs)
    budget = 3000
    minimum_runs = -(-total // budget)  # ceil -> 7

    seen: set[int] = set()
    cursors: list[int] = []
    runs = 0
    while seen != set(range(1, 201)):
        picked, cursors = select_chunks_for_budget(cs, budget, cursors=cursors)
        seen.update(_pages(picked))
        runs += 1
        assert runs <= minimum_runs * 2, "the sweep is not converging"
    assert runs <= minimum_runs + 2


def test_a_run_actually_uses_its_budget():
    # The remainder of every share is handed out, otherwise a sweep needs more runs.
    cs = _chunks(200, 100)
    picked, _ = select_chunks_for_budget(cs, 3000)
    used = sum(len(c["content"]) + 1 for c in picked)
    assert used <= 3000
    assert used >= 3000 * 0.9


def test_sweep_wraps_around_instead_of_running_dry():
    # At the end the marks start over instead of delivering nothing.
    cs = _chunks(60, 100)
    cursors: list[int] = []
    for _ in range(20):
        picked, cursors = select_chunks_for_budget(cs, 1500, cursors=cursors)
        assert picked, "a run must never come back empty"


def test_stored_cursors_of_the_wrong_length_are_survivable():
    # A changed block count costs at most one uneven run.
    cs = _chunks(120, 100)
    picked, cursors = select_chunks_for_budget(cs, 3000, cursors=[1, 2, 3])
    assert picked
    assert len(cursors) == _COVERAGE_BLOCKS


def test_a_source_barely_over_budget_is_almost_read_out_in_one_run():
    # Almost every block fits entirely and starts over right away.
    cs = _chunks(20, 100)
    first, cursors = select_chunks_for_budget(cs, 2000)
    assert len(first) == 19  # all but the one the budget cannot hold
    assert cursors.count(0) >= _COVERAGE_BLOCKS - 1

    second, _ = select_chunks_for_budget(cs, 2000, cursors=cursors)
    assert set(_pages(first)) | set(_pages(second)) == set(range(1, 21))


def test_a_chunk_larger_than_its_share_is_still_read():
    # Skipping would park the mark in front of it forever.
    cs = [{"page_number": i + 1, "content": "x" * 5000} for i in range(24)]
    picked, cursors = select_chunks_for_budget(cs, 1200)  # 100 chars per block
    assert picked
    assert cursors != [0] * _COVERAGE_BLOCKS  # every block moved on
