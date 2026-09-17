"""Die Datentabelle mit Anweisung: Block im Prompt, Treffer statt Pakete, Marke bei daneben."""

import json
import types

import pytest

from src.features.ai_assistant.tasks import _instruction as anweisung
from src.features.ai_assistant.tasks.studio.data_table import run_generate_data_table


CHUNKS = {
    1: [{"page_number": 1, "content": "Alles aus A."}, {"page_number": 3, "content": "Aus A."}],
    2: [{"page_number": 2, "content": "Alles aus B."}],
}
STELLE_A = {"source_id": 1, "page_number": 3, "content": "Aus A."}
SOURCE_MAP = {"1": {"number": 1, "filename": "a.pdf", "uuid": "u1"},
              "2": {"number": 2, "filename": "b.pdf", "uuid": "u2"}}
ANTWORT = json.dumps({"title": "T", "columns": ["x", "y", "z"], "rows": [{"cells": ["1", "2", "3"]}]})


@pytest.fixture
def stack(monkeypatch):
    """Hooks the table up to stubs and records what the model was asked."""
    import src.features.ai_assistant.tasks.studio.data_table as mod

    seen = {"messages": [], "condensed": 0, "unmatched": [], "saved": []}
    row = {"id": 1, "workspace_id": 7, "user_instruction": ""}

    class _DB:
        def get_aia_data_table(self, _id):
            return dict(row)

        def update_aia_data_table(self, did, status, **kwargs):
            seen["saved"].append((status, kwargs.get("error")))

        def get_chunks_by_source(self, sid):
            return list(CHUNKS.get(sid, []))

        def get_aia_source(self, uuid):
            nummer = 1 if uuid == "u1" else 2
            return {"id": nummer, "filename": SOURCE_MAP[str(nummer)]["filename"],
                    "workspace_id": 7, "summary": None}

        def set_instruction_unmatched(self, table, row_id, unmatched):
            seen["unmatched"].append((table, row_id, unmatched))

    monkeypatch.setattr(mod, "db", _DB())
    monkeypatch.setattr(mod, "tool_context_budget", lambda: 10_000)
    monkeypatch.setattr(mod, "_get_llm_client", lambda: (object(), "m", "p"))

    def _create(client, *, model, messages, endpoint="tool", **kwargs):
        seen["messages"].append(messages)
        message = types.SimpleNamespace(content=ANTWORT)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])

    monkeypatch.setattr(mod, "create_logged", _create)

    def _condensed_build(**kwargs):
        seen["condensed"] += 1
        return json.loads(ANTWORT)

    monkeypatch.setattr(mod._condensed, "should_condense", lambda *a: False)
    monkeypatch.setattr(mod._condensed, "build", _condensed_build)
    # The condensed way fetches an embedding provider before it ever calls build(), even
    # when build() itself is stubbed below, so a real provider is never actually needed.
    monkeypatch.setattr("src.services.aia_embeddings.get_embedding_provider_with_fallback",
                        lambda: types.SimpleNamespace(embed_one=lambda text: [0.0]))
    monkeypatch.setattr("src.features.ai_assistant.tasks._helpers.learning_tools_language",
                        lambda: ("de", "German"))
    monkeypatch.setattr("src.services.aia_adaptive_tools.build_adaptive_tool_suffix",
                        lambda uid: "")
    monkeypatch.setattr("src.features.ai_assistant.tasks.studio._attribution.attribute_studio_claims",
                        lambda claims, **k: [[] for _ in claims])
    monkeypatch.setattr("src.features.ai_assistant.tasks._titles.resolve_title",
                        lambda *a, **k: "Titel")
    monkeypatch.setattr("src.features.ai_assistant.tasks.studio._result_title.recent_titles",
                        lambda *a, **k: [])

    def _mit(wahl):
        monkeypatch.setattr(mod, "resolve_instruction", lambda *a, **k: wahl)

    return mod, seen, row, _mit


def _run():
    run_generate_data_table(1, [1, 2], ["u1", "u2"], SOURCE_MAP, locale="de", user_id=3)


def test_without_an_instruction_the_prompt_is_as_before(stack):
    mod, seen, row, mit = stack
    mit(anweisung.Resolution("", None, False, anweisung.NONE))
    _run()
    system, user = seen["messages"][0][0]["content"], seen["messages"][0][1]["content"]
    assert "ADDITIONAL INSTRUCTION" not in system
    assert "Alles aus A." in user and "Alles aus B." in user
    assert seen["unmatched"] == []
    assert seen["saved"][-1][0] == "success"


def test_a_style_instruction_lands_in_every_packet_prompt(stack):
    mod, seen, row, mit = stack
    row["user_instruction"] = "Spalten: Begriff, Frist"
    mit(anweisung.Resolution("Spalten: Begriff, Frist", None, False, anweisung.STYLE))
    _run()
    block = anweisung.prompt_block("Spalten: Begriff, Frist")
    assert all(block in nachricht[0]["content"] for nachricht in seen["messages"])
    assert "Alles aus B." in seen["messages"][0][1]["content"]
    # Every run writes the flag anew, so a retry that hits the material clears an old miss.
    assert seen["unmatched"] == [("aia_data_tables", 1, False)]


def test_a_topic_instruction_narrows_the_material_to_the_found_spots(stack):
    mod, seen, row, mit = stack
    row["user_instruction"] = "nur A"
    mit(anweisung.Resolution("nur A", [STELLE_A], False, anweisung.SEARCH))
    mod._condensed.should_condense = lambda *a: True
    _run()
    system, user = seen["messages"][0][0]["content"], seen["messages"][0][1]["content"]
    assert "Aus A." in user
    assert "Alles aus A." not in user and "b.pdf" not in user
    assert "nur A" in system
    assert "must be about what the instruction names" in system
    assert seen["condensed"] == 0
    assert len(seen["messages"]) == 1


def test_the_condensed_way_carries_the_block_too(stack):
    mod, seen, row, mit = stack
    row["user_instruction"] = "kurze Zellen"
    mit(anweisung.Resolution("kurze Zellen", None, False, anweisung.STYLE))
    mod._condensed.should_condense = lambda *a: True
    gesehen = {}

    def _build(**kwargs):
        gesehen.update(kwargs)
        return json.loads(ANTWORT)

    mod._condensed.build = _build
    _run()
    assert gesehen["adaptive_suffix"].endswith(anweisung.prompt_block("kurze Zellen"))


def test_an_unmatched_instruction_marks_the_row_and_stays_out_of_the_prompt(stack):
    mod, seen, row, mit = stack
    row["user_instruction"] = "Quantenphysik"
    mit(anweisung.Resolution("", None, True, anweisung.UNMATCHED))
    _run()
    assert seen["unmatched"] == [("aia_data_tables", 1, True)]
    assert "ADDITIONAL INSTRUCTION" not in seen["messages"][0][0]["content"]
    assert seen["saved"][-1][0] == "success"
