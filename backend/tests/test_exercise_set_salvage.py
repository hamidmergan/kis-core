"""No later step may throw finished work away."""

import pytest

from src.features.ai_assistant.tasks.language_training import run_generate_exercise_set


_ITEMS = [{"front": "a", "back": "A"}, {"front": "b", "back": "B"}]


@pytest.fixture
def stack(monkeypatch):
    """Hooks the job up to stubs and records what lands in the database."""
    import src.features.ai_assistant.tasks.language_training as mod

    seen = {"finalized": None, "failed": False}

    class _DB:
        def get_aia_workspace_by_id(self, _id):
            return {"id": 7}

        def get_exercise_set_with_items(self, _id):
            return {"user_id": 1, "grammar_type": None}

        def finalize_exercise_set(self, set_id, title, items, header=None, user_id=None):
            seen["finalized"] = {"title": title, "items": items, "header": header}

        def fail_exercise_set(self, _id):
            seen["failed"] = True

    monkeypatch.setattr(mod, "db", _DB())
    monkeypatch.setattr(mod, "_get_llm_client", lambda: (object(), "m", "p"))
    monkeypatch.setattr(mod, "build_adaptive_tool_suffix", lambda *a, **k: "")
    monkeypatch.setattr(mod, "build_title_avoidance_block", lambda *a, **k: "")
    monkeypatch.setattr(mod, "resolve_set_title", lambda *a, **k: "Endgültig")
    monkeypatch.setattr(mod, "coverage_rule", lambda *a, **k: "")
    monkeypatch.setattr(mod, "missing_section_uuids", lambda *a, **k: ["u-2"])
    monkeypatch.setattr(mod, "per_section_quota", lambda *a, **k: 2)

    class _Ctx:
        sections = {1: "A.pdf", 2: "B.pdf"}
        source_by_name = {"A.pdf": {"id": 1}}

    monkeypatch.setattr(mod, "build_source_context", lambda *a, **k: _Ctx())
    monkeypatch.setattr(mod, "generate_mc_from_source",
                        lambda *a, **k: (list(_ITEMS), "Vorläufig"))
    return mod, seen


def _run():
    run_generate_exercise_set(1, 7, "quiz", "source", 2, source_uuids=["u-1"])


def test_a_failing_top_up_keeps_the_items_that_are_already_finished(stack, monkeypatch):
    """The top-up fails, the finished exercises are saved anyway."""
    mod, seen = stack
    calls = {"n": 0}

    def _generate(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] > 1:
            raise RuntimeError("Connection error.")
        return list(_ITEMS), "Vorläufig"

    monkeypatch.setattr(mod, "generate_mc_from_source", _generate)

    _run()

    assert seen["failed"] is False
    assert [i["front"] for i in seen["finalized"]["items"]] == ["a", "b"]


def test_a_failing_title_call_keeps_the_provisional_name(stack, monkeypatch):
    # The title is cosmetics, a lost set is not.
    mod, seen = stack
    monkeypatch.setattr(mod, "missing_section_uuids", lambda *a, **k: [])

    def _boom(*a, **k):
        raise RuntimeError("Connection error.")

    monkeypatch.setattr(mod, "resolve_set_title", _boom)

    _run()

    assert seen["failed"] is False
    assert seen["finalized"]["title"] == "Vorläufig"


def test_a_failing_first_run_still_fails_the_set(stack, monkeypatch):
    # Without a single exercise there is nothing to salvage.
    mod, seen = stack

    def _boom(*a, **k):
        raise RuntimeError("Connection error.")

    monkeypatch.setattr(mod, "generate_mc_from_source", _boom)

    _run()

    assert seen["failed"] is True
    assert seen["finalized"] is None
