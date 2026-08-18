"""Concurrent pre-search for post-hoc citation attribution.

The per-sentence chips search the DB once per sentence/clause. Done
sequentially that is the dominant cost of the post-answer pause (measured ~13.7s
of a ~15.3s pause). The searches hit LOCAL Postgres (not the embed API), so they
can run concurrently. ``_parallel_search`` runs one search
per UNIQUE line across a thread pool and returns a ``{line: hits}`` map the
sequential attribution walk then just looks up. Correctness is unchanged: the
map holds exactly what ``search_fn`` would have returned per line; a failing
search maps to ``[]`` (same as the caller's own guarded search).
"""
import time

from src.features.ai_assistant.routes._helpers import _parallel_search


def test_returns_one_result_per_line():
    def fake(line):
        return [{"id": line.upper()}]

    got = _parallel_search(["alpha", "beta", "gamma"], fake, max_workers=4)
    assert got == {
        "alpha": [{"id": "ALPHA"}],
        "beta": [{"id": "BETA"}],
        "gamma": [{"id": "GAMMA"}],
    }


def test_dedupes_repeated_lines_searched_once():
    calls = []

    def fake(line):
        calls.append(line)
        return [line]

    got = _parallel_search(["a", "a", "b", "a"], fake, max_workers=4)
    assert got == {"a": ["a"], "b": ["b"]}
    # "a" appears three times in the input but is searched exactly once.
    assert sorted(calls) == ["a", "b"]


def test_search_exception_maps_to_empty_list():
    # A single failing search must not sink the batch — that line gets [] (exactly
    # what the caller's guarded _search_one returns on error) and the rest survive.
    def fake(line):
        if line == "boom":
            raise RuntimeError("db down")
        return [line]

    got = _parallel_search(["ok", "boom", "fine"], fake, max_workers=2)
    assert got == {"ok": ["ok"], "boom": [], "fine": ["fine"]}


def test_empty_input_returns_empty_map():
    assert _parallel_search([], lambda l: [l], max_workers=4) == {}


def test_blank_lines_are_skipped():
    # Empty / whitespace-only "lines" are never real candidates; don't waste a search.
    calls = []

    def fake(line):
        calls.append(line)
        return [line]

    got = _parallel_search(["real", "", "   "], fake, max_workers=4)
    assert got == {"real": ["real"]}
    assert calls == ["real"]


def test_runs_concurrently_not_sequentially():
    # The whole point of the change: 8 searches that each block 0.1s finish in ~0.1s
    # (concurrent), not ~0.8s (sequential). This is the behaviour we are adding.
    def fake(line):
        time.sleep(0.1)
        return [line]

    lines = [str(i) for i in range(8)]
    t0 = time.perf_counter()
    got = _parallel_search(lines, fake, max_workers=8)
    elapsed = time.perf_counter() - t0
    assert len(got) == 8
    assert elapsed < 0.5  # 8 x 0.1s sequential would be ~0.8s
