from src.features.ai_assistant.scheduling.scheduler import WeightedAreaSelector


def test_weighted_split_matches_weights():
    sel = WeightedAreaSelector({"chat": 2.0, "ingest": 1.0, "studio": 1.0})
    demand = {"chat": 1000, "ingest": 1000, "studio": 1000}
    counts = {"chat": 0, "ingest": 0, "studio": 0}
    for _ in range(400):
        counts[sel.pick(demand)] += 1
    assert 180 <= counts["chat"] <= 220
    assert 80 <= counts["ingest"] <= 120
    assert 80 <= counts["studio"] <= 120


def test_work_conserving_idle_area_skipped():
    sel = WeightedAreaSelector({"chat": 2.0, "ingest": 1.0})
    demand = {"chat": 10, "ingest": 0}
    picks = [sel.pick(demand) for _ in range(10)]
    assert set(picks) == {"chat"}


def test_returns_none_when_no_demand():
    sel = WeightedAreaSelector({"chat": 1.0})
    assert sel.pick({"chat": 0}) is None


def test_zero_weight_area_never_picked():
    sel = WeightedAreaSelector({"chat": 1.0, "bg": 0.0})
    demand = {"chat": 5, "bg": 5}
    picks = [sel.pick(demand) for _ in range(5)]
    assert set(picks) == {"chat"}
