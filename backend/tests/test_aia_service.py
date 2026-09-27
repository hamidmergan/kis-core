from src.features.ai_assistant.scheduling.dispatch_service import (
    DispatchService,
    InMemoryJobStore,
)
from src.features.ai_assistant.scheduling.service import (
    area_for_task,
    enqueue_task,
    scheduler_enabled,
    slots_from_settings,
    weights_from_settings,
)


def test_area_for_task():
    assert area_for_task("aia.generate_mindmap") == "studio"
    assert area_for_task("aia.generate_data_table") == "studio"
    assert area_for_task("aia.index_source") == "ingest"
    assert area_for_task("aia.reindex_workspace") == "ingest"
    assert area_for_task("aia.unknown") == "ingest"  # safe default


def test_scheduler_ist_immer_an():
    """The toggle was a migration aid and is gone."""
    assert scheduler_enabled(get_setting=lambda k, d="": d) is True
    assert scheduler_enabled(get_setting=lambda k, d="": "false") is True


def test_plaetze_kommen_aus_der_maschine_nicht_aus_einer_einstellung():
    """A setting can no longer override the detected machine size."""
    from src.limits import AIA_PARALLEL_SLOTS

    assert slots_from_settings(get_setting=lambda k, d="": d) == AIA_PARALLEL_SLOTS
    assert slots_from_settings(get_setting=lambda k, d="": "99") == AIA_PARALLEL_SLOTS
    assert AIA_PARALLEL_SLOTS >= 1


def test_weights_default_and_override():
    assert weights_from_settings(get_setting=lambda k, d="": d) == {"studio": 1.0, "ingest": 2.0}
    custom = weights_from_settings(get_setting=lambda k, d="": '{"studio": 3, "ingest": 1}')
    assert custom == {"studio": 3.0, "ingest": 1.0}


def test_enqueue_task_routes_to_area_and_dispatches():
    store = InMemoryJobStore()
    launched: list[tuple[str, str]] = []
    svc = DispatchService(
        store=store,
        launch=lambda j: (launched.append((j.task_name, j.area)) or "tid"),
        total_slots=2,
        weights={"studio": 1.0, "ingest": 1.0},
    )
    juid = enqueue_task(
        "aia.generate_mindmap", user_id=5, args=[1, 2], kwargs={"locale": "de"}, service=svc
    )
    job = store.get(juid)
    assert job.area == "studio"
    assert job.user_id == 5
    assert job.payload == {"args": [1, 2], "kwargs": {"locale": "de"}}
    assert launched == [("aia.generate_mindmap", "studio")]


def test_plaetze_sind_in_jedem_prozess_gleich():
    """The pool is shared, so the number has to be the same everywhere."""
    from src import limits

    assert isinstance(limits.AIA_PARALLEL_SLOTS, int)
    assert limits.AIA_PARALLEL_SLOTS >= 1
    # Not derivable from machine detection, it no longer knows this value.
    from src.services.system_capacity import Capacity

    assert not hasattr(Capacity, "parallel_slots")
