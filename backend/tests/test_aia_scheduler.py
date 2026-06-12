from src.features.ai_assistant.scheduling.fair_dispatch import QueuedJob
from src.features.ai_assistant.scheduling.scheduler import (
    AreaState,
    WeightedAreaSelector,
    plan_dispatch,
)


# ---- plan_dispatch: per-area isolation + per-user fairness ----

def test_plan_isolates_areas_by_own_cap():
    areas = [
        AreaState(
            "ingest",
            concurrency=2,
            queued=[QueuedJob("i1", 1, 1.0), QueuedJob("i2", 1, 2.0), QueuedJob("i3", 1, 3.0)],
            running_user_ids=[],
        ),
        AreaState(
            "studio",
            concurrency=1,
            queued=[QueuedJob("s1", 1, 1.0)],
            running_user_ids=[],
        ),
    ]
    plan = plan_dispatch(areas)
    assert plan["ingest"] == ["i1", "i2"]  # its own cap of 2
    assert plan["studio"] == ["s1"]  # independent cap of 1


def test_plan_respects_running_slots():
    areas = [AreaState("ingest", concurrency=2, queued=[QueuedJob("i1", 1, 1.0)], running_user_ids=[1])]
    assert plan_dispatch(areas)["ingest"] == ["i1"]  # 1 running, 1 free


def test_plan_user_fairness_within_area():
    # user 1 flooded, user 2 has one; one free slot goes to user 2
    queued = [QueuedJob(f"u1-{i}", 1, float(i)) for i in range(10)] + [QueuedJob("u2", 2, 99.0)]
    areas = [AreaState("ingest", concurrency=2, queued=queued, running_user_ids=[1])]
    assert plan_dispatch(areas)["ingest"] == ["u2"]


# ---- WeightedAreaSelector: work-conserving weighted budget split ----

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
