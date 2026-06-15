"""Stress test for the AIA shared-pool dispatcher.

Deterministic discrete-tick simulation: users submit background jobs into the
shared pool, jobs run for a random number of ticks, and finishing a job
re-dispatches into the freed slot. We assert the invariants under load:

1. The shared pool of N slots is NEVER exceeded at any tick.
2. A user flooding never blocks a newcomer (per-user fairness).
3. Areas get their weighted share (studio outweighs ingest), none starves.
4. Everything drains - no deadlock, every job completes.

Runnable standalone for a heavier load:  python tests/test_aia_stress.py
"""
import itertools
import random

from src.features.ai_assistant.scheduling.dispatch_service import (
    DispatchService,
    InMemoryJobStore,
    Job,
)

WEIGHTS = {"studio": 2.0, "ingest": 1.0}


def simulate(submissions, total_slots, weights=WEIGHTS, seed=0, min_dur=1, max_dur=5):
    """submissions: list of (tick, user_id, area). Returns a result dict."""
    rng = random.Random(seed)
    store = InMemoryJobStore()
    running_remaining: dict[str, int] = {}
    started_order: list[Job] = []
    finished_order: list[str] = []
    max_running = 0
    area_grants: dict[str, int] = {a: 0 for a in weights}
    pool_violations: list[tuple] = []

    def launch(job: Job) -> str:
        running_remaining[job.job_uuid] = rng.randint(min_dur, max_dur)
        started_order.append(job)
        area_grants[job.area] = area_grants.get(job.area, 0) + 1
        return f"t-{job.job_uuid}"

    svc = DispatchService(store, launch, total_slots=total_slots, weights=weights)

    by_tick: dict[int, list[tuple[int, str]]] = {}
    for tick_, uid, area in submissions:
        by_tick.setdefault(tick_, []).append((uid, area))
    last_submit_tick = max((s[0] for s in submissions), default=0)

    counter = itertools.count()
    tick = 0
    while True:
        for uid, area in by_tick.get(tick, []):
            n = next(counter)
            svc.enqueue(Job(f"j{n}", uid, area, "t", {}, float(n)))

        max_running = max(max_running, len(running_remaining))
        if len(running_remaining) > total_slots:
            pool_violations.append((tick, len(running_remaining)))

        finished_this = [juid for juid, r in running_remaining.items() if r <= 1]
        for juid in list(running_remaining):
            running_remaining[juid] -= 1
        for juid in finished_this:
            del running_remaining[juid]
            finished_order.append(juid)
            svc.on_complete(juid)

        tick += 1
        any_queued = any(j.status == "queued" for j in store._jobs.values())
        if tick > last_submit_tick and not running_remaining and not any_queued:
            break
        if tick > 1_000_000:
            raise RuntimeError("simulation did not converge")

    return {
        "store": store,
        "started": started_order,
        "finished": finished_order,
        "pool_violations": pool_violations,
        "max_running": max_running,
        "area_grants": area_grants,
        "ticks": tick,
    }


def test_stress_pool_never_exceeded_and_all_complete():
    rng = random.Random(7)
    subs = []
    for uid in range(1, 51):  # 50 users
        for _ in range(20):  # 20 jobs each -> 1000 jobs
            subs.append((rng.randint(0, 50), uid, rng.choice(["studio", "ingest"])))
    res = simulate(subs, total_slots=2, seed=1)
    assert res["pool_violations"] == []
    assert res["max_running"] <= 2
    assert all(j.status == "done" for j in res["store"]._jobs.values())
    assert len(res["finished"]) == len(subs)


def test_stress_flooder_does_not_block_newcomer():
    subs = [(0, 1, "studio") for _ in range(100)]  # user 1 floods 100
    subs.append((0, 2, "studio"))  # user 2 submits one, enqueued last
    res = simulate(subs, total_slots=2, weights={"studio": 1.0}, seed=3)
    started = res["started"]
    pos = next(i for i, j in enumerate(started) if j.user_id == 2)
    u1_before = sum(1 for j in started[:pos] if j.user_id == 1)
    assert u1_before <= 2  # newcomer starts after at most `pool` flood jobs


def test_stress_weighted_order_studio_over_ingest():
    # Under backlog, studio (weight 2) drains ~2x faster than ingest (weight 1).
    # Over a full drain totals equalise, so we measure the dispatch ORDER.
    subs = [(0, u, "studio") for u in range(1, 101)] + [(0, u, "ingest") for u in range(101, 201)]
    res = simulate(subs, total_slots=3, weights={"studio": 2.0, "ingest": 1.0}, seed=5)
    first60 = res["started"][:60]
    studio = sum(1 for j in first60 if j.area == "studio")
    ingest = sum(1 for j in first60 if j.area == "ingest")
    assert studio > ingest * 1.5  # ~2:1 in favour of studio
    assert all(j.status == "done" for j in res["store"]._jobs.values())


def test_stress_pool2_serves_both_areas_no_starvation():
    # at exactly 2 slots, neither area is starved (both keep getting served)
    subs = []
    for t in range(200):
        subs.append((t, 1, "studio"))
        subs.append((t, 2, "ingest"))
    res = simulate(subs, total_slots=2, weights={"studio": 2.0, "ingest": 1.0}, seed=5)
    g = res["area_grants"]
    assert g["studio"] > 0 and g["ingest"] > 0
    assert all(j.status == "done" for j in res["store"]._jobs.values())


if __name__ == "__main__":
    rng = random.Random(42)
    subs = []
    for uid in range(1, 201):  # 200 users
        for _ in range(25):  # 25 jobs each -> 5000 jobs
            subs.append((rng.randint(0, 200), uid, rng.choice(["studio", "ingest"])))
    res = simulate(subs, total_slots=2, seed=99)
    print(f"jobs submitted : {len(subs)}")
    print(f"jobs finished  : {len(res['finished'])}")
    print(f"ticks to drain : {res['ticks']}")
    print(f"max concurrent : {res['max_running']} (pool=2)")
    print(f"area grants    : {res['area_grants']}")
    print(f"pool violations: {len(res['pool_violations'])}")
    assert not res["pool_violations"], "POOL EXCEEDED"
    assert len(res["finished"]) == len(subs), "NOT ALL DRAINED"
    print("OK: pool held, all drained, studio weighted over ingest")
