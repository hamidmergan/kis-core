"""Unit tests for the SPECIFIC retrieval cost controls:

- ``_allocate_specific_budget`` / ``_take_chunks_within`` — Option 2: one total
  char budget split across on-topic sources, relevance-weighted, with a floor so
  every source is represented. Caps how many of each source's (mostly-noise) hits
  reach the model while keeping a deep fact (an author at rank ~59) and a fact
  spread across many docs (one author per doc).
- ``_pack_context_batches`` — single-batch (GENERIC/SCOPE: drop overflow) vs
  multi-batch (SPECIFIC: spill, never drop), per-batch id restart, media page set.
- ``aia_reduce_user_message`` — map-reduce merge prompt.

All pure functions: no DB, no LLM, fully deterministic/offline.
"""
import pytest

from src.features.ai_assistant.routes.chat import (
    _allocate_specific_budget,
    _take_chunks_within,
    _pack_context_batches,
    _SPECIFIC_FLOOR_CHARS,
)
from src.tool_prompts import aia_reduce_user_message


def _mk(sid, n, *, chars=100, dist=0.5, first_marker=None, page_start=1):
    """n RRF-ranked chunks for one source (rank 0 first). ``first_marker`` tags
    the rank-0 chunk's content so tests can check the top hit survives."""
    hits = []
    for i in range(n):
        content = (first_marker if (first_marker and i == 0) else "noise") + " "
        content = content + "x" * max(0, chars - len(content))
        hits.append({
            "source_id": sid,
            "content": content,
            "page_number": page_start + i,
            "vec_distance": dist,
        })
    return hits


# ── _take_chunks_within ──────────────────────────────────────────────────────

def test_take_chunks_stops_at_share_and_sets_seq():
    hits = _mk(1, 10, chars=100)
    taken = _take_chunks_within(hits, 350)  # ~3 chunks of 100
    assert len(taken) == 3
    assert [c["_seq"] for c in taken] == [0, 1, 2]  # per-source rank preserved


def test_take_chunks_takes_at_least_one_even_if_oversized():
    hits = _mk(1, 5, chars=1000)
    taken = _take_chunks_within(hits, 100)  # share smaller than one chunk
    assert len(taken) == 1  # never represent a source by nothing


# ── _allocate_specific_budget ────────────────────────────────────────────────

def test_allocate_empty():
    assert _allocate_specific_budget([], 10000) == []


def test_allocate_single_source_gets_whole_budget_keeps_deep_hit():
    # One on-topic source with the answer buried at rank 40 → it must survive,
    # because a single source receives the entire budget (no split).
    hits = _mk(7, 60, chars=100)
    hits[40]["content"] = "AUTHOR Mauersberger " + "x" * 80
    out = _allocate_specific_budget([(hits, 0.44)], 250000)
    assert len(out) == 60  # all 60 fit in the budget
    assert any("Mauersberger" in c["content"] for c in out)


def test_allocate_relevance_weighting_favors_more_on_topic_source():
    # A (closer, dist .40) must get materially more chunks than B (farther, .50).
    a = _mk(1, 1000, chars=100, dist=0.40)
    b = _mk(2, 1000, chars=100, dist=0.50)
    out = _allocate_specific_budget([(a, 0.40), (b, 0.50)], 50000)
    n_a = sum(1 for c in out if c["source_id"] == 1)
    n_b = sum(1 for c in out if c["source_id"] == 2)
    assert n_a > n_b
    # total stays within the budget (no silent overshoot beyond ~one chunk/source)
    total_chars = sum(len(c["content"]) for c in out)
    assert total_chars <= 50000 + 2 * 100


def test_allocate_floor_keeps_every_source_represented():
    # 13 docs, each naming a different author at rank 0 + lots of noise. Even on a
    # tight budget the floor must keep all 13 docs (so no author is dropped).
    kept = []
    for k in range(13):
        hits = _mk(1000 + k, 60, chars=100, dist=0.45 + 0.001 * k,
                   first_marker=f"AUTHOR_{k}")
        kept.append((hits, 0.45 + 0.001 * k))
    out = _allocate_specific_budget(kept, 26000)
    present = {c["source_id"] for c in out}
    assert len(present) == 13  # every doc represented
    # every doc's rank-0 (author) chunk is kept (it is taken first)
    authors = {c["content"].split()[0] for c in out if c["content"].startswith("AUTHOR_")}
    assert authors == {f"AUTHOR_{k}" for k in range(13)}


def test_allocate_floor_capped_when_many_sources_tiny_budget():
    # floor must be capped to budget//K so floors can never exceed the budget.
    kept = [( _mk(i, 50, chars=100), 0.5) for i in range(20)]
    out = _allocate_specific_budget(kept, 10000)  # 10000//20 = 500 < _SPECIFIC_FLOOR_CHARS
    total = sum(len(c["content"]) for c in out)
    # 20 sources * at-least-one chunk (100) is the hard floor; stays near budget
    assert total <= 10000 + 20 * 100
    assert len({c["source_id"] for c in out}) == 20


# ── _pack_context_batches ────────────────────────────────────────────────────

_SRCS = {1: {"filename": "a.pdf"}, 2: {"filename": "b.pdf"}}
_S2Q = {1: 1, 2: 2}


def _chunks_for_pack():
    return [
        {"source_id": 1, "page_number": 10, "content": "A" * 500},
        {"source_id": 1, "page_number": 11, "content": "B" * 500},
        {"source_id": 2, "page_number": 20, "content": "C" * 500},
    ]


def test_pack_single_batch_drops_overflow():
    batches, seen = _pack_context_batches(
        _chunks_for_pack(), 700, _S2Q, _SRCS, {}, multi=False)
    assert len(batches) == 1                    # one context only
    assert seen == {1: {10}}                    # only the first chunk fit → page 10


def test_pack_multi_batch_spills_nothing_dropped():
    batches, seen = _pack_context_batches(
        _chunks_for_pack(), 700, _S2Q, _SRCS, {}, multi=True)
    assert len(batches) == 3                    # spilled, never dropped
    assert seen == {1: {10, 11}, 2: {20}}       # union across all batches


def test_pack_multi_restarts_ids_per_batch():
    import re
    batches, _ = _pack_context_batches(
        _chunks_for_pack(), 700, _S2Q, _SRCS, {}, multi=True)
    for b in batches:
        assert re.findall(r'id="(\d+)"', b) == ["1"]  # each batch numbers from 1


def test_pack_media_source_gets_empty_page_set():
    media = [{"source_id": 3, "start_time": 5.0, "end_time": 9.0,
              "content": "M" * 100, "page_number": None}]
    _, seen = _pack_context_batches(
        media, 5000, {3: 1}, {3: {"filename": "v.mp4"}}, {}, multi=True)
    assert seen == {3: set()}  # timestamp chip has no page to validate → accept


def test_pack_empty_chunks():
    batches, seen = _pack_context_batches([], 5000, {}, {}, {}, multi=True)
    assert batches == []
    assert seen == {}


# ── aia_reduce_user_message ──────────────────────────────────────────────────

def test_reduce_message_contains_question_and_all_partials():
    msg = aia_reduce_user_message("Wer sind die Autoren?",
                                  ["Anna Schmidt.", "Boris Klein."])
    assert "Wer sind die Autoren?" in msg
    assert "Anna Schmidt." in msg
    assert "Boris Klein." in msg


def test_reduce_message_states_keep_every_fact_rule():
    msg = aia_reduce_user_message("q", ["p1", "p2"])
    low = msg.lower()
    assert "at least one" in low      # keep a fact present in any partial
    assert "ignore" in low            # drop "not in the sources" partials
