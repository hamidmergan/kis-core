"""Unit tests for the SPECIFIC retrieval cost controls:

- ``_take_chunks_within`` — fuellt eine nach Note sortierte Liste bis zur Grenze auf
  und nimmt mindestens eine Stelle, auch wenn sie allein schon zu gross ist.
- ``_pack_context_batches`` — single batch fuer jeden Weg: was nicht mehr passt,
  faellt raus. Dazu die Seitenmenge und der leere Fall bei Medien.

All pure functions: no DB, no LLM, fully deterministic/offline.
"""
import pytest

from src.features.ai_assistant.routes.chat import (
    _take_chunks_within,
    _pack_context_batches,
)


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

# Die Tests von ``_allocate_specific_budget`` standen hier bis zum 16.08.2026. Die
# Funktion ist weg: der Platz wird nicht mehr in Stufen nach Quellen verteilt, sondern
# global nach Note vergeben. Was sie leisten sollte, haelt jetzt der Messsatz fest
# (scripts/rag_retrieval_eval.py), und zwar an echten Quellen statt an ausgedachten
# Zahlen. Die vier Waechterfaelle fuer Vergleichsfragen sind genau dafuer da.


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
        _chunks_for_pack(), 700, _S2Q, _SRCS, {})
    assert len(batches) == 1                    # one context only
    assert seen == {1: {10}}                    # only the first chunk fit → page 10


def test_pack_never_opens_a_second_batch():
    import re
    batches, _ = _pack_context_batches(
        _chunks_for_pack(), 700, _S2Q, _SRCS, {})
    assert len(batches) == 1                          # es gibt keinen zweiten Weg mehr
    assert re.findall(r'id="(\d+)"', batches[0]) == ["1"]  # nummeriert ab 1


def test_pack_media_source_gets_empty_page_set():
    media = [{"source_id": 3, "start_time": 5.0, "end_time": 9.0,
              "content": "M" * 100, "page_number": None}]
    _, seen = _pack_context_batches(
        media, 5000, {3: 1}, {3: {"filename": "v.mp4"}}, {})
    assert seen == {3: set()}  # timestamp chip has no page to validate → accept


def test_pack_empty_chunks():
    batches, seen = _pack_context_batches([], 5000, {}, {}, {})
    assert batches == []
    assert seen == {}
