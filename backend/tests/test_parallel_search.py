"""The line searches run concurrently, the result stays the same."""
import time

from src.features.ai_assistant.routes._evidence import _parallel_search


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
    # A failed search must not take the batch down with it.
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
    # Eight searches together take as long as one.
    def fake(line):
        time.sleep(0.1)
        return [line]

    lines = [str(i) for i in range(8)]
    t0 = time.perf_counter()
    got = _parallel_search(lines, fake, max_workers=8)
    elapsed = time.perf_counter() - t0
    assert len(got) == 8
    assert elapsed < 0.5  # 8 x 0.1s sequential would be ~0.8s
