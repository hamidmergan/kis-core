"""Ist das Material ausgeschöpft, bekommt die Person Wiederholungen statt eines gescheiterten Satzes.

Lasttest 26.09.: Testpersonen erzeugten viele Kartensätze aus derselben kleinen Folie. Das Modell
lieferte nur noch Karten, die sie schon hatten, alle wurden aussortiert, der Satz scheiterte ohne
Erklärung.
"""

import pytest

from src.features.ai_assistant.tasks.language_training import run_generate_exercise_set

_ITEMS = [{"front": "a", "back": "A"}, {"front": "b", "back": "B"}]


@pytest.fixture
def stack(monkeypatch):
    import src.features.ai_assistant.tasks.language_training as mod

    seen = {"finalized": None, "failed": False}

    class _DB:
        def get_aia_workspace_by_id(self, _id):
            return {"id": 7}

        def get_exercise_set_with_items(self, _id):
            return {"user_id": 1}

        def finalize_exercise_set(self, set_id, title, items, header=None, user_id=None):
            seen["finalized"] = items

        def fail_exercise_set(self, _id):
            seen["failed"] = True

    class _Ctx:
        sections = {1: "A.pdf"}
        source_by_name = {"A.pdf": {"id": 1}}

    monkeypatch.setattr(mod, "db", _DB())
    monkeypatch.setattr(mod, "_get_llm_client", lambda: (object(), "m", "p"))
    monkeypatch.setattr(mod, "build_adaptive_tool_suffix", lambda *a, **k: "")
    monkeypatch.setattr(mod, "build_title_avoidance_block", lambda *a, **k: "")
    monkeypatch.setattr(mod, "resolve_set_title", lambda *a, **k: "Titel")
    monkeypatch.setattr(mod, "coverage_rule", lambda *a, **k: "")
    monkeypatch.setattr(mod, "uses_pool", lambda *a, **k: False)
    monkeypatch.setattr(mod, "build_source_context", lambda *a, **k: _Ctx())
    monkeypatch.setattr(mod, "generate_mc_from_source", lambda *a, **k: ([dict(i) for i in _ITEMS], "Titel"))
    return mod, seen


def test_nur_wiederholungen_ergeben_trotzdem_einen_satz(stack, monkeypatch):
    mod, seen = stack
    monkeypatch.setattr(mod, "seen_by_user", lambda *a, **k: ["a", "b"])

    run_generate_exercise_set(1, 7, "quiz", "source", 2, source_uuids=["u-1"])

    assert seen["failed"] is False
    assert sorted(i["front"] for i in seen["finalized"]) == ["a", "b"]


def test_eine_wiederholung_fuellt_nur_die_luecke(stack, monkeypatch):
    mod, seen = stack
    monkeypatch.setattr(mod, "seen_by_user", lambda *a, **k: ["a"])

    run_generate_exercise_set(1, 7, "quiz", "source", 2, source_uuids=["u-1"])

    # One new card and exactly one repeat for the single missing place.
    assert sorted(i["front"] for i in seen["finalized"]) == ["a", "b"]


def test_ohne_luecke_kommt_keine_wiederholung_dazu(stack, monkeypatch):
    mod, seen = stack
    monkeypatch.setattr(mod, "seen_by_user", lambda *a, **k: [])

    run_generate_exercise_set(1, 7, "quiz", "source", 2, source_uuids=["u-1"])

    assert [i["front"] for i in seen["finalized"]] == ["a", "b"]
