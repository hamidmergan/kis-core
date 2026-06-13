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


def test_scheduler_disabled_by_default():
    assert scheduler_enabled(get_setting=lambda k, d="": d) is False
    assert scheduler_enabled(get_setting=lambda k, d="": "false") is False
    assert scheduler_enabled(get_setting=lambda k, d="": "true") is True
    assert scheduler_enabled(get_setting=lambda k, d="": "TRUE") is True


def test_slots_default_from_limits():
    # default falls through to the limits.py constant (2)
    assert slots_from_settings(get_setting=lambda k, d="": d) == 2
    assert slots_from_settings(get_setting=lambda k, d="": "5") == 5
    assert slots_from_settings(get_setting=lambda k, d="": "0") == 0  # unlimited


def test_weights_default_and_override():
    assert weights_from_settings(get_setting=lambda k, d="": d) == {"studio": 2.0, "ingest": 1.0}
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
