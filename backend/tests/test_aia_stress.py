"""Stress test for the AIA dispatch engine.

Deterministic discrete-tick simulation: users submit jobs into lanes, jobs run
for a random number of ticks, and finishing a job re-dispatches the lane. We
assert the invariants that matter under load:

1. Per-lane concurrency cap is NEVER exceeded at any tick.
2. A user flooding a lane never blocks a newcomer (fair-share).
3. Lanes are isolated: an ingest flood never starves studio.
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


def simulate(submissions, caps, seed=0, min_dur=1, max_dur=5):
    """submissions: list of (tick, user_id, area). Returns a result dict."""
    rng = random.Random(seed)
    store = InMemoryJobStore()
    running_remaining: dict[str, int] = {}
    started_order: list[Job] = []
    finished_order: list[str] = []
    max_running_per_area = {a: 0 for a in caps}
    cap_violations: list[tuple] = []

    def launch(job: Job) -> str:
        running_remaining[job.job_uuid] = rng.randint(min_dur, max_dur)
        started_order.append(job)
        return f"t-{job.job_uuid}"

    svc = DispatchService(store, launch, caps)

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

        # invariant: running per lane <= cap
        per_area = {a: 0 for a in caps}
        for juid in running_remaining:
            per_area[store.get(juid).area] += 1
        for a, c in per_area.items():
            max_running_per_area[a] = max(max_running_per_area[a], c)
            if c > caps[a]:
                cap_violations.append((tick, a, c))

        # advance one tick: decrement, then finish + re-dispatch
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
        "cap_violations": cap_violations,
        "max_running_per_area": max_running_per_area,
        "ticks": tick,
    }


def test_stress_no_cap_violation_and_all_complete():
    caps = {"ingest": 2, "studio": 4}
    rng = random.Random(7)
    subs = []
    for uid in range(1, 51):  # 50 users
        for _ in range(20):  # 20 jobs each -> 1000 jobs
            subs.append((rng.randint(0, 50), uid, rng.choice(["ingest", "studio"])))
    res = simulate(subs, caps, seed=1)
    assert res["cap_violations"] == []
    assert res["max_running_per_area"]["ingest"] <= 2
    assert res["max_running_per_area"]["studio"] <= 4
    assert all(j.status == "done" for j in res["store"]._jobs.values())
    assert len(res["finished"]) == len(subs)


def test_stress_flooder_does_not_block_newcomer():
    caps = {"ingest": 2}
    subs = [(0, 1, "ingest") for _ in range(100)]  # user 1 floods 100
    subs.append((0, 2, "ingest"))  # user 2 submits one, enqueued last
    res = simulate(subs, caps, seed=3)
    started = res["started"]
    pos = next(i for i, j in enumerate(started) if j.user_id == 2)
    u1_before = sum(1 for j in started[:pos] if j.user_id == 1)
    assert u1_before <= caps["ingest"]  # newcomer starts after at most `cap` flood jobs


def test_stress_area_isolation_ingest_flood_keeps_studio_flowing():
    caps = {"ingest": 1, "studio": 4}
    subs = [(0, 1, "ingest") for _ in range(50)]  # ingest flooded by one user
    subs += [(0, uid, "studio") for uid in range(2, 22)]  # 20 studio users
    res = simulate(subs, caps, seed=5)
    assert res["cap_violations"] == []
    assert res["max_running_per_area"]["studio"] == 4  # studio not starved
    assert all(j.status == "done" for j in res["store"]._jobs.values())


if __name__ == "__main__":
    caps = {"ingest": 2, "studio": 4}
    rng = random.Random(42)
    subs = []
    for uid in range(1, 201):  # 200 users
        for _ in range(25):  # 25 jobs each -> 5000 jobs
            subs.append((rng.randint(0, 200), uid, rng.choice(["ingest", "studio"])))
    res = simulate(subs, caps, seed=99)
    print(f"jobs submitted : {len(subs)}")
    print(f"jobs finished  : {len(res['finished'])}")
    print(f"ticks to drain : {res['ticks']}")
    print(f"max concurrent : {res['max_running_per_area']}")
    print(f"cap violations : {len(res['cap_violations'])}")
    assert not res["cap_violations"], "CAP VIOLATED"
    assert len(res["finished"]) == len(subs), "NOT ALL DRAINED"
    print("OK: cap held, all drained, lanes isolated")
