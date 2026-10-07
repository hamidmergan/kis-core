"""Die Mindmap mit Anweisung: Block im Prompt, Treffer statt Volltext, Marke bei daneben."""

import types

import pytest

from src.features.ai_assistant.tasks import _instruction as anweisung
from src.features.ai_assistant.tasks.studio.mindmap import run_generate_mindmap


CHUNKS_A = [{"page_number": 1, "content": "Alles aus A."}, {"page_number": 3, "content": "Aus A."}]
CHUNKS_B = [{"page_number": 2, "content": "Alles aus B."}]
STELLE_A = {"source_id": 1, "page_number": 3, "content": "Aus A."}


@pytest.fixture
def stack(monkeypatch):
    """Hooks the map up to stubs and records what the model was asked."""
    import src.features.ai_assistant.tasks.studio.mindmap as mod

    seen = {"messages": [], "condensed": 0, "unmatched": [], "saved": []}
    row = {"id": 1, "workspace_id": 7, "user_instruction": ""}

    class _DB:
        def get_aia_mindmap(self, _id):
            return dict(row)

        def update_aia_mindmap(self, mid, status, mindmap=None, error=None, title=None):
            seen["saved"].append((status, error))

        def get_aia_source(self, uuid):
            nummer = 1 if uuid == "u1" else 2
            return {"id": nummer, "filename": f"{uuid}.pdf", "workspace_id": 7, "summary": None}

        def set_instruction_unmatched(self, table, row_id, unmatched):
            seen["unmatched"].append((table, row_id, unmatched))

    monkeypatch.setattr(mod, "db", _DB())
    monkeypatch.setattr(mod, "_collect_sources", lambda ids, uuids: [
        (1, "u1.pdf", CHUNKS_A, CHUNKS_A), (2, "u2.pdf", CHUNKS_B, CHUNKS_B)])
    monkeypatch.setattr(mod, "tool_context_budget", lambda: 10_000)
    monkeypatch.setattr("src.features.ai_assistant.tasks._context_budget.small_model", lambda: False)
    monkeypatch.setattr(mod, "build_adaptive_tool_suffix", lambda uid: "")

    def _ask(client, model, messages, mid):
        seen["messages"].append(messages)
        return {"topic": "T", "children": []}

    monkeypatch.setattr(mod, "_ask_json", _ask)

    def _condensed_build(**kwargs):
        seen["condensed"] += 1
        return {"topic": "T", "children": []}

    monkeypatch.setattr(mod._condensed, "should_condense", lambda *a: False)
    monkeypatch.setattr(mod._condensed, "build", _condensed_build)
    # The condensed way fetches an embedding provider before it ever calls build(), even
    # when build() itself is stubbed below, so a real provider is never actually needed.
    monkeypatch.setattr("src.services.aia_embeddings.get_embedding_provider_with_fallback",
                        lambda: types.SimpleNamespace(embed_one=lambda text: [0.0]))
    from src.services.feature_router import FeatureBinding
    monkeypatch.setattr("src.dependencies._resolve_llm_binding",
                        lambda: FeatureBinding(feature="chat", model="m",
                                               provider={"base_url": "http://modell", "name": "p", "api_key": "k"}))
    monkeypatch.setattr("src.features.ai_assistant.tasks._helpers.learning_tools_language",
                        lambda: ("de", "German"))
    monkeypatch.setattr("src.features.ai_assistant.tasks._titles.resolve_title",
                        lambda *a, **k: "Titel")
    monkeypatch.setattr("src.features.ai_assistant.tasks.studio._result_title.recent_titles",
                        lambda *a, **k: [])

    def _mit(wahl):
        monkeypatch.setattr(mod, "resolve_instruction", lambda *a, **k: wahl)

    return mod, seen, row, _mit


def _run():
    run_generate_mindmap(1, [1, 2], ["u1", "u2"], locale="de", user_id=3)


def test_without_an_instruction_the_prompt_is_as_before(stack):
    mod, seen, row, mit = stack
    mit(anweisung.Resolution("", None, False, anweisung.NONE))
    _run()
    system, user = seen["messages"][0][0]["content"], seen["messages"][0][1]["content"]
    assert "ADDITIONAL INSTRUCTION" not in system
    assert "Alles aus A." in user and "Alles aus B." in user
    assert seen["unmatched"] == []
    assert seen["saved"][-1][0] == "success"


def test_a_style_instruction_lands_in_the_system_prompt_with_all_material(stack):
    mod, seen, row, mit = stack
    row["user_instruction"] = "nur drei Ebenen"
    mit(anweisung.Resolution("nur drei Ebenen", None, False, anweisung.STYLE))
    _run()
    system, user = seen["messages"][0][0]["content"], seen["messages"][0][1]["content"]
    assert system.endswith(anweisung.prompt_block("nur drei Ebenen"))
    assert "Alles aus A." in user and "Alles aus B." in user
    # Every run writes the flag anew, so a retry that hits the material clears an old miss.
    assert seen["unmatched"] == [("aia_mindmaps", 1, False)]


def test_a_topic_instruction_narrows_the_material_to_the_found_spots(stack):
    mod, seen, row, mit = stack
    row["user_instruction"] = "nur A"
    mit(anweisung.Resolution("nur A", [STELLE_A], False, anweisung.SEARCH))
    # Even oversized material takes the single call, the spots already fit.
    mod._condensed.should_condense = lambda *a: True
    _run()
    system, user = seen["messages"][0][0]["content"], seen["messages"][0][1]["content"]
    assert "Aus A." in user
    assert "Alles aus A." not in user and "Alles aus B." not in user
    assert "u2.pdf" not in user
    assert "nur A" in system
    assert "must be about what the instruction names" in system
    assert seen["condensed"] == 0


def test_the_condensed_way_carries_the_block_too(stack):
    mod, seen, row, mit = stack
    row["user_instruction"] = "kurze Labels"
    mit(anweisung.Resolution("kurze Labels", None, False, anweisung.STYLE))
    mod._condensed.should_condense = lambda *a: True
    gesehen = {}

    def _build(**kwargs):
        gesehen.update(kwargs)
        return {"topic": "T", "children": []}

    mod._condensed.build = _build
    _run()
    assert gesehen["adaptive_suffix"].endswith(anweisung.prompt_block("kurze Labels"))


def test_an_unmatched_instruction_marks_the_row_and_stays_out_of_the_prompt(stack):
    mod, seen, row, mit = stack
    row["user_instruction"] = "Quantenphysik"
    mit(anweisung.Resolution("", None, True, anweisung.UNMATCHED))
    _run()
    assert seen["unmatched"] == [("aia_mindmaps", 1, True)]
    assert "ADDITIONAL INSTRUCTION" not in seen["messages"][0][0]["content"]
    assert seen["saved"][-1][0] == "success"
