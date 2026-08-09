"""Chunk selection for the AIA tools' context window.

A source that fits goes in whole. An oversized source is read as a SWEEP: one window per
coverage block, resuming where the previous run stopped, always returned in document
order. The properties that matter are coverage (every chunk is eventually read, including
the very first and the very last) and progress (no run repeats the previous one).
"""

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
    # Taking the first chunks only would bias every exercise to page 1. One window per
    # block means a single run spans the document.
    cs = _chunks(120, 100)
    picked, _ = select_chunks_for_budget(cs, 3000)
    pages = _pages(picked)
    assert max(pages) > 80  # something from the last third
    assert min(pages) < 40  # and the front


def test_first_run_starts_at_the_very_first_chunk():
    # The random sampler this replaced anchored each block at a random offset and only
    # grew forward, so everything before the first anchor was unreachable: on a real
    # 489-page PDF page 1 came up once in 30 runs. A sweep starts at the start.
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
    """The whole document gets read, and roughly as fast as the budget allows.

    Not exactly the arithmetic minimum: the blocks are one chunk apart in width, so they
    reach their end on different runs and whoever finishes first starts over while the
    others are still going. The overhead is small and bounded, and it disappears as the
    chunks get small against the per-block share, which is the production case: on a real
    2.18M-char PDF against an 800k budget the sweep hits the minimum of three runs exactly.
    """
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
    # Handing every block a fixed share and stopping there wastes the remainder of each
    # share, which showed up as the sweep needing more runs than the budget called for.
    cs = _chunks(200, 100)
    picked, _ = select_chunks_for_budget(cs, 3000)
    used = sum(len(c["content"]) + 1 for c in picked)
    assert used <= 3000
    assert used >= 3000 * 0.9


def test_sweep_wraps_around_instead_of_running_dry():
    # Past the end of the document the cursors start over rather than returning nothing,
    # so a workspace that keeps generating keeps getting material.
    cs = _chunks(60, 100)
    cursors: list[int] = []
    for _ in range(20):
        picked, cursors = select_chunks_for_budget(cs, 1500, cursors=cursors)
        assert picked, "a run must never come back empty"


def test_stored_cursors_of_the_wrong_length_are_survivable():
    # The block count changes when a source is re-uploaded shorter than the block count.
    # An old row must cost at most one uneven run, never an exception.
    cs = _chunks(120, 100)
    picked, cursors = select_chunks_for_budget(cs, 3000, cursors=[1, 2, 3])
    assert picked
    assert len(cursors) == _COVERAGE_BLOCKS


def test_a_source_barely_over_budget_is_almost_read_out_in_one_run():
    # 2020 chars against a 2000 budget. Nearly every block holds its whole width, so most
    # of them wrap straight back to their start, and the two runs together have seen the
    # document twice over rather than stalling on the one chunk that did not fit.
    cs = _chunks(20, 100)
    first, cursors = select_chunks_for_budget(cs, 2000)
    assert len(first) == 19  # all but the one the budget cannot hold
    assert cursors.count(0) >= _COVERAGE_BLOCKS - 1

    second, _ = select_chunks_for_budget(cs, 2000, cursors=cursors)
    assert set(_pages(first)) | set(_pages(second)) == set(range(1, 21))


def test_a_chunk_larger_than_its_share_is_still_read():
    # Skipping it would park that block's cursor in front of it forever and the material
    # behind it would never be reached.
    cs = [{"page_number": i + 1, "content": "x" * 5000} for i in range(24)]
    picked, cursors = select_chunks_for_budget(cs, 1200)  # 100 chars per block
    assert picked
    assert cursors != [0] * _COVERAGE_BLOCKS  # every block moved on
