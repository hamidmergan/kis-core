"""Die Routen reichen die Anweisung gesaeubert an die Zeile durch und geben sie zurueck."""

import types

import pytest

from src.features.ai_assistant import schemas
from src.features.ai_assistant.routes.language_training import exercises as sets_route
from src.features.ai_assistant.routes.studio import data_table as table_route
from src.features.ai_assistant.routes.studio import mindmap as mindmap_route


USER = {"user_id": 3, "role": "user", "is_admin": False}
WORKSPACE = {"id": 7, "user_id": 3, "uuid": "w1"}


def _quiet(monkeypatch, mod):
    """Access, burst and quota are somebody else's test."""
    monkeypatch.setattr(mod.db, "get_aia_workspace", lambda uuid: dict(WORKSPACE))
    monkeypatch.setattr(mod.db, "is_student_enrolled", lambda w, u: False)
    monkeypatch.setattr(mod.db, "get_aia_source",
                        lambda uuid: {"id": 1, "uuid": uuid, "filename": "a.pdf", "status": "ready"})
    monkeypatch.setattr(mod, "enforce_aia_burst", lambda *a, **k: None)
    monkeypatch.setattr(mod, "enforce_quota", lambda *a, **k: None)
    monkeypatch.setattr(mod, "_resolve_source_ids", lambda *a, **k: [1])


def _stub_task(monkeypatch, path):
    calls = []
    monkeypatch.setattr(path, types.SimpleNamespace(delay=lambda *a, **k: calls.append((a, k))))
    return calls


# --- Mindmap ---------------------------------------------------------------------

@pytest.fixture
def mindmap(monkeypatch):
    _quiet(monkeypatch, mindmap_route)
    angelegt = []
    monkeypatch.setattr(mindmap_route.db, "create_aia_mindmap",
                        lambda *a, **k: (angelegt.append((a, k)), 11)[1])
    monkeypatch.setattr("src.features.ai_assistant.scheduling.service.scheduler_enabled",
                        lambda: False)
    _stub_task(monkeypatch, "src.tasks.aia_tasks.run_generate_mindmap")
    return angelegt


@pytest.mark.asyncio
async def test_the_mindmap_route_stores_the_cleaned_instruction(mindmap):
    body = schemas.MindmapGenerateBody(active_source_ids=["u1"], instruction="  nur   Kapitel 3 ")
    antwort = await mindmap_route.generate_mindmap("w1", body, current_user=USER, locale="de")
    assert antwort["mindmap_id"] == 11
    assert mindmap[0][1]["user_instruction"] == "nur Kapitel 3"


@pytest.mark.asyncio
async def test_the_mindmap_route_stores_nothing_without_an_instruction(mindmap):
    body = schemas.MindmapGenerateBody(active_source_ids=["u1"])
    await mindmap_route.generate_mindmap("w1", body, current_user=USER, locale="de")
    assert mindmap[0][1]["user_instruction"] is None


@pytest.mark.asyncio
async def test_the_mindmap_answer_carries_instruction_and_flag(monkeypatch):
    _quiet(monkeypatch, mindmap_route)
    zeile = {"id": 11, "workspace_id": 7, "status": "success", "mindmap": {"topic": "T"},
             "error": None, "source_ids": [1], "user_instruction": "nur Kapitel 3",
             "instruction_unmatched": True}
    monkeypatch.setattr(mindmap_route.db, "get_aia_mindmap", lambda mid: dict(zeile))
    monkeypatch.setattr(mindmap_route.db, "get_latest_aia_mindmap", lambda w, u: dict(zeile))
    monkeypatch.setattr(mindmap_route.db, "get_aia_source_by_id", lambda sid: {"filename": "a.pdf"})
    einzeln = await mindmap_route.get_mindmap("w1", 11, current_user=USER, locale="de")
    letzte = await mindmap_route.get_latest_mindmap("w1", current_user=USER, locale="de")
    for antwort in (einzeln, letzte):
        assert antwort["user_instruction"] == "nur Kapitel 3"
        assert antwort["instruction_unmatched"] is True


# --- Datentabelle ----------------------------------------------------------------

@pytest.fixture
def table(monkeypatch):
    _quiet(monkeypatch, table_route)
    angelegt = []
    monkeypatch.setattr(table_route.db, "create_aia_data_table",
                        lambda *a, **k: (angelegt.append((a, k)), 12)[1])
    _stub_task(monkeypatch, "src.tasks.aia_tasks.run_generate_data_table")
    return angelegt


@pytest.mark.asyncio
async def test_the_table_route_stores_the_cleaned_instruction(table):
    body = schemas.DataTableGenerateBody(active_source_ids=["u1"], instruction=" nur  Fristen ")
    antwort = await table_route.generate_data_table("w1", body, current_user=USER, locale="de")
    assert antwort["data_table_id"] == 12
    assert table[0][1]["user_instruction"] == "nur Fristen"


@pytest.mark.asyncio
async def test_the_table_route_stores_nothing_without_an_instruction(table):
    body = schemas.DataTableGenerateBody(active_source_ids=["u1"])
    await table_route.generate_data_table("w1", body, current_user=USER, locale="de")
    assert table[0][1]["user_instruction"] is None


# --- Karteikarten und Quiz -----------------------------------------------------

@pytest.fixture
def sets(monkeypatch):
    _quiet(monkeypatch, sets_route)
    angelegt = []
    monkeypatch.setattr(sets_route.db, "create_exercise_set_placeholder",
                        lambda **k: (angelegt.append(k), {"id": 13})[1])
    monkeypatch.setattr(sets_route.db, "is_language_training_ready", lambda u: True)
    _stub_task(monkeypatch, "src.tasks.aia_tasks.run_generate_exercise_set")
    return angelegt


@pytest.mark.asyncio
@pytest.mark.parametrize("tool", ["quiz", "karteikarten"])
async def test_the_set_route_stores_the_instruction_for_the_two_tools(sets, tool):
    body = schemas.CreateSetBody(tool=tool, mode="source", source_uuids=["u1"], count=5,
                                 instruction=" leichte  Fragen ")
    await sets_route.create_exercise_set("w1", body, current_user=USER, locale="de")
    assert sets[0]["user_instruction"] == "leichte Fragen"


@pytest.mark.asyncio
async def test_the_set_route_ignores_the_instruction_for_other_tools(sets):
    body = schemas.CreateSetBody(tool="flashcards", mode="source", source_uuids=["u1"],
                                 instruction="leichte Fragen")
    await sets_route.create_exercise_set("w1", body, current_user=USER, locale="de")
    assert sets[0]["user_instruction"] is None


@pytest.mark.asyncio
async def test_the_set_route_ignores_the_instruction_in_glossary_mode(sets):
    body = schemas.CreateSetBody(tool="quiz", mode="glossary", instruction="leichte Fragen")
    await sets_route.create_exercise_set("w1", body, current_user=USER, locale="de")
    assert sets[0]["user_instruction"] is None
