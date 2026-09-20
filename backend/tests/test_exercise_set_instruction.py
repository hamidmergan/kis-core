"""Karteikarten und Quiz mit Anweisung: kein Vorrat, gefundene Stellen statt Sweep, Block im Prompt."""

import json
import types

import pytest

from src.features.ai_assistant.tasks import _instruction as anweisung
from src.features.ai_assistant.tasks.language_training import (
    _source_cards,
    _source_mc,
    run_generate_exercise_set,
)
from src.features.ai_assistant.tasks.language_training._context import (
    build_context_from_chunks,
)


# --- build_context_from_chunks -------------------------------------------------

def _install_sources(monkeypatch, names):
    by_uuid = {f"u{i}": {"id": i, "filename": name, "workspace_id": 1, "uuid": f"u{i}"}
               for i, name in enumerate(names, start=1)}
    monkeypatch.setattr("src.database.get_aia_source", lambda u: by_uuid.get(u))
    return list(by_uuid)


def test_the_found_spots_become_numbered_sections_in_the_chosen_order(monkeypatch):
    uuids = _install_sources(monkeypatch, ["a.pdf", "b.pdf", "c.pdf"])
    chunks = [
        {"source_id": 3, "page_number": 9, "content": "Aus C."},
        {"source_id": 1, "page_number": 3, "content": "Aus A."},
    ]
    ctx = build_context_from_chunks(uuids, chunks)
    assert ctx.sections == {1: "a.pdf", 2: "c.pdf"}
    assert "[a.pdf, S. 3] Aus A." in ctx.context
    assert "[c.pdf, S. 9] Aus C." in ctx.context
    # The source without a hit is not in the material and not in the legend.
    assert "b.pdf" not in ctx.context
    assert set(ctx.source_by_name) == {"a.pdf", "c.pdf"}
    assert ctx.seen_pages_by_source == {1: {3}, 3: {9}}
    assert ctx.multi_label == "2 Sources"


def test_a_single_hit_source_reads_like_a_single_source(monkeypatch):
    uuids = _install_sources(monkeypatch, ["a.pdf", "b.pdf"])
    ctx = build_context_from_chunks(uuids, [{"source_id": 2, "page_number": 1, "content": "B."}])
    assert ctx.sections == {1: "b.pdf"}
    assert ctx.multi_label == "b.pdf"
    assert ctx.first_label == "b.pdf"
    assert ctx.context.startswith("--- b.pdf ---")


def test_media_spots_keep_their_start_time(monkeypatch):
    uuids = _install_sources(monkeypatch, ["v.webm"])
    ctx = build_context_from_chunks(
        uuids, [{"source_id": 1, "page_number": 4, "content": "Ton.", "start_time": 12.5}])
    assert ctx.media_start_by_page == {1: {4: 12.5}}


def test_without_any_hit_there_is_no_context(monkeypatch):
    uuids = _install_sources(monkeypatch, ["a.pdf"])
    assert build_context_from_chunks(uuids, []) is None
    assert build_context_from_chunks(uuids, [{"source_id": 9, "page_number": 1, "content": "x"}]) is None


# --- the block reaches the generators -----------------------------------------

def _client(content):
    calls = []

    def create(model, messages, **kwargs):
        calls.append(messages)
        message = types.SimpleNamespace(content=content)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])

    return types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create))), calls


def _ctx():
    return types.SimpleNamespace(source_hint="Quelle", context="ctx", multi_label="T")


def test_the_quiz_appends_the_instruction_block_to_its_system_prompt(monkeypatch):
    monkeypatch.setattr(_source_mc, "_attach_by_kind", lambda *a, **k: None)
    client, calls = _client(json.dumps({"title": "T", "exercises": [
        {"question": "Was?", "options": ["a", "b", "c", "d"], "correct_idx": 0}]}))
    block = anweisung.prompt_block("nur Kapitel 3")
    _source_mc.generate_mc_from_source(client, "m", _ctx(), 1, instruction=block)
    assert calls[0][0]["content"].endswith(block)
    assert "nur Kapitel 3" not in calls[0][1]["content"]


def test_the_quiz_split_yields_to_an_instruction(monkeypatch):
    """Without an instruction the thirds are a counted order, with one they are the default."""
    monkeypatch.setattr(_source_mc, "_attach_by_kind", lambda *a, **k: None)
    client, calls = _client(json.dumps({"title": "T", "exercises": []}))
    _source_mc.generate_mc_from_source(client, "m", _ctx(), 6)
    fest = calls[0][0]["content"]
    assert "Create exactly 2 comprehension questions, 2 gap sentences and 2 true/false" in fest
    _source_mc.generate_mc_from_source(client, "m", _ctx(), 6,
                                       instruction=anweisung.prompt_block("nur Richtig oder Falsch"))
    frei = calls[1][0]["content"]
    assert "Create exactly" not in frei
    assert "6 exercises in total" in frei
    assert "particular kinds" in frei


def test_the_quiz_prompt_is_unchanged_without_an_instruction(monkeypatch):
    monkeypatch.setattr(_source_mc, "_attach_by_kind", lambda *a, **k: None)
    client, calls = _client(json.dumps({"title": "T", "exercises": []}))
    _source_mc.generate_mc_from_source(client, "m", _ctx(), 1)
    assert "ADDITIONAL INSTRUCTION" not in calls[0][0]["content"]


def test_the_cards_append_the_instruction_block_to_their_system_prompt(monkeypatch):
    monkeypatch.setattr(_source_cards, "attach_chips", lambda *a, **k: None)
    client, calls = _client(json.dumps({"title": "T", "cards": [
        {"question": "Was?", "answer": "Das."}]}))
    block = anweisung.prompt_block("nur Kapitel 3")
    _source_cards.generate_cards_from_source(client, "m", _ctx(), 1, instruction=block)
    assert calls[0][0]["content"].endswith(block)


# --- the task: pool, way and flag ----------------------------------------------

STELLE = {"source_id": 1, "page_number": 3, "content": "Aus A."}


@pytest.fixture
def stack(monkeypatch):
    """Hooks the job up to stubs and records what the run did with pool and material."""
    import src.features.ai_assistant.tasks.language_training as mod

    seen = {"take": 0, "store": 0, "sweep": 0, "spots": 0, "gen": [], "unmatched": [],
            "resolve": []}
    satz = {"user_id": 1, "grammar_type": None, "grammar_topic_id": None,
            "user_instruction": ""}

    class _DB:
        def get_aia_workspace_by_id(self, _id):
            return {"id": 7}

        def get_exercise_set_with_items(self, _id):
            return dict(satz)

        def get_aia_source(self, uuid):
            return {"id": 1, "uuid": uuid, "filename": "a.pdf", "workspace_id": 7}

        def finalize_exercise_set(self, *a, **k):
            pass

        def fail_exercise_set(self, _id):
            raise AssertionError("der Satz darf hier nicht scheitern")

        def set_instruction_unmatched(self, table, row_id, unmatched):
            seen["unmatched"].append((table, row_id, unmatched))

    monkeypatch.setattr(mod, "db", _DB())
    monkeypatch.setattr(mod, "_get_llm_client", lambda: (object(), "m", "p"))
    monkeypatch.setattr(mod, "build_adaptive_tool_suffix", lambda *a, **k: "")
    monkeypatch.setattr(mod, "build_title_avoidance_block", lambda *a, **k: "")
    monkeypatch.setattr(mod, "resolve_set_title", lambda *a, **k: "Endgueltig")
    monkeypatch.setattr(mod, "seen_by_user", lambda *a, **k: [])
    monkeypatch.setattr(mod, "exercise_context_budget", lambda count: 1000)

    def _take(*a, **k):
        seen["take"] += 1
        return []

    def _store(*a, **k):
        seen["store"] += 1

    monkeypatch.setattr(mod, "take_from_pool", _take)
    monkeypatch.setattr(mod, "store_in_pool", _store)

    class _Ctx:
        sections = {1: "a.pdf", 2: "b.pdf"}
        source_by_name = {"a.pdf": {"id": 1, "uuid": "u1"}, "b.pdf": {"id": 2, "uuid": "u2"}}

    def _sweep(*a, **k):
        seen["sweep"] += 1
        return _Ctx()

    def _spots(*a, **k):
        seen["spots"] += 1
        return _Ctx()

    monkeypatch.setattr(mod, "build_source_context", _sweep)
    monkeypatch.setattr(mod, "build_context_from_chunks", _spots)
    monkeypatch.setattr(mod, "missing_section_uuids", lambda *a, **k: [])

    def _gen(client, model, ctx, count, **kwargs):
        seen["gen"].append(kwargs)
        return [{"front": "a", "back": "A", "_section": 1}], "T"

    monkeypatch.setattr(mod, "generate_mc_from_source", _gen)
    monkeypatch.setattr(mod, "generate_cards_from_source", _gen)

    def _mit(wahl):
        def _resolve(workspace_id, source_ids, text, budget):
            seen["resolve"].append((workspace_id, source_ids, text, budget))
            return wahl
        monkeypatch.setattr(mod, "resolve_instruction", _resolve)

    return mod, seen, satz, _mit


def _run(tool="quiz"):
    run_generate_exercise_set(5, 7, tool, "source", 6, source_uuids=["u1"])


def test_without_an_instruction_the_run_is_as_before(stack):
    mod, seen, satz, mit = stack
    mit(anweisung.Resolution("", None, False, anweisung.NONE))
    _run()
    # The stub delivers one exercise for six, so the repeat fallback asks the pool again.
    assert seen["take"] >= 1 and seen["store"] == 1
    assert seen["sweep"] == 1 and seen["spots"] == 0
    assert seen["gen"][0]["instruction"] == ""
    assert seen["unmatched"] == []


def test_a_style_instruction_skips_the_pool_and_keeps_the_sweep(stack):
    mod, seen, satz, mit = stack
    satz["user_instruction"] = "leichte Fragen"
    mit(anweisung.Resolution("leichte Fragen", None, False, anweisung.STYLE))
    _run()
    assert seen["resolve"] == [(7, [1], "leichte Fragen", 1000)]
    assert seen["take"] == 0 and seen["store"] == 0
    assert seen["sweep"] == 1 and seen["spots"] == 0
    assert "leichte Fragen" in seen["gen"][0]["instruction"]
    assert "must be about what the instruction names" not in seen["gen"][0]["instruction"]
    # The quota keeps working on the sweep, the material is the same as ever.
    assert "COVERAGE" in seen["gen"][0]["coverage"]
    # Every run writes the flag anew, so a retry that hits the material clears an old miss.
    assert seen["unmatched"] == [("aia_exercise_sets", 5, False)]


def test_a_topic_instruction_takes_the_found_spots_without_a_quota(stack):
    mod, seen, satz, mit = stack
    satz["user_instruction"] = "nur Kapitel 3"
    mit(anweisung.Resolution("nur Kapitel 3", [STELLE], False, anweisung.SEARCH))
    _run(tool="karteikarten")
    assert seen["take"] == 0 and seen["store"] == 0
    assert seen["sweep"] == 0 and seen["spots"] == 1
    assert "nur Kapitel 3" in seen["gen"][0]["instruction"]
    assert "must be about what the instruction names" in seen["gen"][0]["instruction"]
    assert seen["gen"][0]["coverage"] == ""
    assert seen["unmatched"] == [("aia_exercise_sets", 5, False)]


def test_an_unmatched_instruction_is_dropped_and_the_set_is_marked(stack):
    mod, seen, satz, mit = stack
    satz["user_instruction"] = "erklaere Quantenphysik"
    mit(anweisung.Resolution("", None, True, anweisung.UNMATCHED))
    _run()
    # Dropped means: the pool is back, the prompt carries nothing, the flag is set.
    assert seen["take"] >= 1 and seen["store"] == 1
    assert seen["sweep"] == 1 and seen["spots"] == 0
    assert seen["gen"][0]["instruction"] == ""
    assert seen["unmatched"] == [("aia_exercise_sets", 5, True)]
