import itertools

from src.features.ai_assistant.scheduling.dispatch_service import (
    DispatchService,
    InMemoryJobStore,
    Job,
)

_counter = itertools.count()


def _mk(area: str, user_id: int) -> Job:
    n = next(_counter)
    return Job(
        job_uuid=f"j{n}",
        user_id=user_id,
        area=area,
        task_name="t",
        payload={},
        created_at=float(n),
    )


def _make(caps):
    store = InMemoryJobStore()
    launched: list[str] = []

    def launch(job: Job) -> str:
        launched.append(job.job_uuid)
        return f"task-{job.job_uuid}"

    return DispatchService(store=store, launch=launch, areas_config=caps), store, launched


def test_enqueue_within_cap_launches_immediately():
    svc, store, launched = _make({"ingest": 2})
    job = _mk("ingest", 1)
    svc.enqueue(job)
    assert launched == [job.job_uuid]
    assert store.get(job.job_uuid).status == "running"


def test_enqueue_beyond_cap_queues_then_runs_on_complete():
    svc, store, launched = _make({"ingest": 1})
    a, b = _mk("ingest", 1), _mk("ingest", 1)
    svc.enqueue(a)
    svc.enqueue(b)
    assert launched == [a.job_uuid]
    assert store.get(b.job_uuid).status == "queued"
    svc.on_complete(a.job_uuid)
    assert launched == [a.job_uuid, b.job_uuid]
    assert store.get(a.job_uuid).status == "done"


def test_cap_never_exceeded():
    svc, store, launched = _make({"ingest": 2})
    for uid in [1, 2, 3, 4, 5]:
        svc.enqueue(_mk("ingest", uid))
    running = [j for j in store._jobs.values() if j.status == "running"]
    assert len(running) == 2


def test_area_isolation():
    svc, store, launched = _make({"ingest": 1, "studio": 1})
    i, s = _mk("ingest", 1), _mk("studio", 1)
    svc.enqueue(i)
    svc.enqueue(s)
    assert set(launched) == {i.job_uuid, s.job_uuid}


def test_user_fairness_flooder_does_not_block_newcomer():
    svc, store, launched = _make({"ingest": 2})
    flood = [_mk("ingest", 1) for _ in range(5)]
    for j in flood:
        svc.enqueue(j)
    assert len(launched) == 2  # cap 2, rest queued
    newcomer = _mk("ingest", 2)
    svc.enqueue(newcomer)
    svc.on_complete(launched[0])
    # the freed slot must go to the newcomer, not user 1's backlog
    assert launched[2] == newcomer.job_uuid


def test_failed_job_frees_slot():
    svc, store, launched = _make({"ingest": 1})
    a, b = _mk("ingest", 1), _mk("ingest", 1)
    svc.enqueue(a)
    svc.enqueue(b)
    svc.on_complete(a.job_uuid, ok=False, error="boom")
    assert store.get(a.job_uuid).status == "failed"
    assert store.get(a.job_uuid).error == "boom"
    assert launched == [a.job_uuid, b.job_uuid]
