"""Chunk selection for the AIA tools' context window: a source that fits goes in whole,
an oversized source is sampled as contiguous windows spread across the WHOLE document with
a per-run jitter (coverage + variation), always returned in document order."""

import random

from src.features.ai_assistant.tasks._context_budget import (
    select_chunks_for_budget,
    rotating_focus,
)


def _chunks(n: int, size: int = 100) -> list[dict]:
    return [{"page_number": i + 1, "content": "x" * size} for i in range(n)]


def test_returns_all_when_it_fits():
    cs = _chunks(10, 100)
    assert select_chunks_for_budget(cs, 100000) == cs


def test_empty_in_empty_out():
    assert select_chunks_for_budget([], 1000) == []


def test_oversized_is_trimmed_to_budget():
    cs = _chunks(100, 100)  # ~10100 chars
    out = select_chunks_for_budget(cs, 2000, rng=random.Random(1))
    total = sum(len(c["content"]) + 1 for c in out)
    assert total <= 2000
    assert 0 < len(out) < 100


def test_oversized_covers_whole_document_not_just_front():
    # The old behaviour took the first chunks only, biasing exercises to page 1. Coverage
    # sampling must reach the back of the document too.
    cs = _chunks(120, 100)
    out = select_chunks_for_budget(cs, 3000, rng=random.Random(1))
    pages = [c["page_number"] for c in out]
    assert max(pages) > 80  # something from the last third
    assert min(pages) < 40  # and the front


def test_returned_in_document_order():
    cs = _chunks(120, 100)
    out = select_chunks_for_budget(cs, 3000, rng=random.Random(3))
    pages = [c["page_number"] for c in out]
    assert pages == sorted(pages)


def test_two_runs_sample_differently():
    # Variation: different seeds (i.e. different runs) pick different material, so a second
    # generation does not rehash the first one's chunks.
    cs = _chunks(200, 100)
    a = [c["page_number"] for c in select_chunks_for_budget(cs, 3000, rng=random.Random(1))]
    b = [c["page_number"] for c in select_chunks_for_budget(cs, 3000, rng=random.Random(2))]
    assert a != b


def test_deterministic_for_same_seed():
    cs = _chunks(200, 100)
    a = select_chunks_for_budget(cs, 3000, rng=random.Random(7))
    b = select_chunks_for_budget(cs, 3000, rng=random.Random(7))
    assert a == b


# --- rotating_focus: hard per-run page subset, rotating away from recently-used pages ----

def test_focus_keeps_all_when_too_few_pages():
    # 4 or fewer pages: restricting would barely change anything -> keep all.
    assert rotating_focus([1, 2, 3, 4]) == [1, 2, 3, 4]
    assert rotating_focus([]) == []


def test_focus_returns_sorted_proper_subset():
    pages = list(range(1, 19))  # 18 pages, like the Einführung deck
    out = rotating_focus(pages, rng=random.Random(1))
    assert out == sorted(out)
    assert set(out).issubset(set(pages))
    assert 0 < len(out) < len(pages)  # a real subset so two runs can differ


def test_focus_two_runs_differ():
    pages = list(range(1, 19))
    a = rotating_focus(pages, rng=random.Random(1))
    b = rotating_focus(pages, rng=random.Random(2))
    assert a != b


def test_focus_deterministic_for_same_seed():
    pages = list(range(1, 19))
    assert rotating_focus(pages, rng=random.Random(5)) == rotating_focus(pages, rng=random.Random(5))


def test_focus_prefers_pages_not_recently_used():
    # The pages just questioned (recent) should be avoided when enough fresh pages remain,
    # so the next set draws from other parts of the document.
    pages = list(range(1, 19))
    recent = [1, 2, 3, 4, 5, 6, 7, 8]  # heavily used front
    out = rotating_focus(pages, recent=recent, rng=random.Random(1), fraction=0.5)
    fresh = [p for p in out if p not in recent]
    # the kept set is dominated by fresh (under-used) pages, not the recently-used front
    assert len(fresh) >= len(out) - 1
