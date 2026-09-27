import itertools

from src.features.ai_assistant.scheduling.dispatch_service import (
    DispatchService,
    InMemoryJobStore,
    Job,
)

_counter = itertools.count()
W = {"studio": 1.0, "ingest": 1.0}


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


def _make(total_slots, weights=W):
    store = InMemoryJobStore()
    launched: list[str] = []

    def launch(job: Job) -> str:
        launched.append(job.job_uuid)
        return f"task-{job.job_uuid}"

    return DispatchService(store=store, launch=launch, total_slots=total_slots, weights=weights), store, launched


def test_enqueue_within_pool_launches_immediately():
    svc, store, launched = _make(2)
    job = _mk("studio", 1)
    svc.enqueue(job)
    assert launched == [job.job_uuid]
    assert store.get(job.job_uuid).status == "running"
    assert store.get(job.job_uuid).celery_task_id == f"task-{job.job_uuid}"


def test_enqueue_beyond_pool_queues_then_runs_on_complete():
    svc, store, launched = _make(1)
    a, b = _mk("studio", 1), _mk("studio", 2)
    svc.enqueue(a)
    svc.enqueue(b)
    assert launched == [a.job_uuid]
    assert store.get(b.job_uuid).status == "queued"
    svc.on_complete(a.job_uuid)
    assert launched == [a.job_uuid, b.job_uuid]
    assert store.get(a.job_uuid).status == "done"


def test_pool_size_never_exceeded():
    svc, store, launched = _make(2)
    for uid in [1, 2, 3, 4, 5]:
        svc.enqueue(_mk("studio", uid))
    running = [j for j in store._jobs.values() if j.status == "running"]
    assert len(running) == 2


def test_user_fairness_flooder_does_not_block_newcomer():
    svc, store, launched = _make(2)
    flood = [_mk("studio", 1) for _ in range(5)]
    for j in flood:
        svc.enqueue(j)
    assert len(launched) == 2  # pool of 2, rest queued
    newcomer = _mk("studio", 2)
    svc.enqueue(newcomer)
    svc.on_complete(launched[0])
    # the freed slot must go to the newcomer, not user 1's backlog
    assert launched[2] == newcomer.job_uuid


def test_failed_job_frees_slot():
    svc, store, launched = _make(1)
    a, b = _mk("studio", 1), _mk("studio", 2)
    svc.enqueue(a)
    svc.enqueue(b)
    svc.on_complete(a.job_uuid, ok=False, error="boom")
    assert store.get(a.job_uuid).status == "failed"
    assert store.get(a.job_uuid).error == "boom"
    assert launched == [a.job_uuid, b.job_uuid]


def test_unlimited_pool_runs_everything():
    svc, store, launched = _make(0)  # 0 = unlimited
    for uid in range(10):
        svc.enqueue(_mk("studio", uid))
    assert len(launched) == 10


def _warten(store, area, user_id):
    job = _mk(area, user_id)
    store.add(job)
    return job


def test_viele_kurze_quellen_hungern_ihren_bereich_nicht_aus():
    # Lasttest 26.09.: after 12 short source jobs the sources waited 8 minutes for the mind maps to catch up.
    from src.limits import AIA_AREA_WEIGHTS

    svc, store, launched = _make(4, weights=dict(AIA_AREA_WEIGHTS))
    for uid in range(12):
        fertig = _mk("ingest", uid)
        svc.enqueue(fertig)
        svc.on_complete(fertig.job_uuid)
    for uid in (20, 21, 22):
        svc.enqueue(_mk("studio", uid))
    quelle = _warten(store, "ingest", 30)
    _warten(store, "studio", 31)

    svc.dispatch()

    assert launched[-1] == quelle.job_uuid


def test_mindmaps_bekommen_trotzdem_immer_einen_platz():
    from src.limits import AIA_AREA_WEIGHTS

    svc, store, launched = _make(4, weights=dict(AIA_AREA_WEIGHTS))
    for uid in range(8):
        _warten(store, "ingest", uid)
        _warten(store, "studio", 100 + uid)

    svc.dispatch()

    bereiche = [store.get(j).area for j in launched]
    assert bereiche.count("studio") >= 1 and bereiche.count("ingest") > bereiche.count("studio")


def test_tools_laufen_neben_hoechstens_drei_quellen():
    """Lauf 10: 100 Tools teilten sich 4 Plätze mit Quellen, die letzten warteten über eine halbe Stunde."""
    from src.features.ai_assistant.scheduling.service import get_dispatch_service

    store = InMemoryJobStore()
    launched: list[str] = []
    svc = get_dispatch_service(store=store, launch=lambda job: launched.append(job.job_uuid) or "t")
    for uid in range(8):
        _warten(store, "ingest", uid)
        _warten(store, "studio", 100 + uid)

    svc.dispatch()

    bereiche = [store.get(j).area for j in launched]
    assert bereiche.count("ingest") == 3
    assert bereiche.count("studio") >= 3
