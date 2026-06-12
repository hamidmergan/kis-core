from src.features.ai_assistant.scheduling.dispatch_service import (
    DispatchService,
    InMemoryJobStore,
)
from src.features.ai_assistant.scheduling.service import (
    area_for_task,
    caps_from_settings,
    enqueue_task,
    scheduler_enabled,
)


def test_area_for_task():
    assert area_for_task("aia.generate_mindmap") == "studio"
    assert area_for_task("aia.generate_glossary") == "studio"
    assert area_for_task("aia.index_source") == "ingest"
    assert area_for_task("aia.reindex_workspace") == "ingest"
    assert area_for_task("aia.unknown") == "ingest"  # safe default


def test_scheduler_disabled_by_default():
    assert scheduler_enabled(get_setting=lambda k, d="": d) is False
    assert scheduler_enabled(get_setting=lambda k, d="": "false") is False
    assert scheduler_enabled(get_setting=lambda k, d="": "true") is True
    assert scheduler_enabled(get_setting=lambda k, d="": "TRUE") is True


def test_caps_defaults():
    assert caps_from_settings(get_setting=lambda k, d="": d) == {"ingest": 2, "studio": 4}


def test_caps_custom():
    s = {"aia_ingest_concurrency": "3", "aia_studio_concurrency": "7"}
    assert caps_from_settings(get_setting=lambda k, d="": s.get(k, d)) == {"ingest": 3, "studio": 7}


def test_enqueue_task_routes_to_area_and_dispatches():
    store = InMemoryJobStore()
    launched: list[tuple[str, str]] = []
    svc = DispatchService(
        store=store,
        launch=lambda j: (launched.append((j.task_name, j.area)) or "tid"),
        areas_config={"ingest": 2, "studio": 2},
    )
    juid = enqueue_task(
        "aia.generate_glossary", user_id=5, args=[1, 2], kwargs={"locale": "de"}, service=svc
    )
    job = store.get(juid)
    assert job.area == "studio"
    assert job.user_id == 5
    assert job.payload == {"args": [1, 2], "kwargs": {"locale": "de"}}
    assert launched == [("aia.generate_glossary", "studio")]
