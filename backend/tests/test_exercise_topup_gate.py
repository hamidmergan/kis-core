"""The top-up for skipped sections only runs while the quota was asked for."""

import pytest

from src.features.ai_assistant.tasks.language_training import run_generate_exercise_set


@pytest.fixture
def stack(monkeypatch):
    """Hooks the job up to stubs and records whether the top-up was considered."""
    import src.features.ai_assistant.tasks.language_training as mod

    seen = {"gefragt": 0, "laeufe": 0}

    class _DB:
        def get_aia_workspace_by_id(self, _id):
            return {"id": 7}

        def get_exercise_set_with_items(self, _id):
            return {"user_id": 1, "grammar_type": None, "grammar_topic_id": None}

        def finalize_exercise_set(self, *a, **k):
            pass

        def fail_exercise_set(self, _id):
            raise AssertionError("der Satz darf hier nicht scheitern")

    monkeypatch.setattr(mod, "db", _DB())
    monkeypatch.setattr(mod, "_get_llm_client", lambda: (object(), "m", "p"))
    monkeypatch.setattr(mod, "build_adaptive_tool_suffix", lambda *a, **k: "")
    monkeypatch.setattr(mod, "build_title_avoidance_block", lambda *a, **k: "")
    monkeypatch.setattr(mod, "resolve_set_title", lambda *a, **k: "Endgueltig")
    monkeypatch.setattr(mod, "take_from_pool", lambda *a, **k: [])
    monkeypatch.setattr(mod, "seen_by_user", lambda *a, **k: [])
    monkeypatch.setattr(mod, "store_in_pool", lambda *a, **k: None)

    def _missing(*a, **k):
        seen["gefragt"] += 1
        return []

    monkeypatch.setattr(mod, "missing_section_uuids", _missing)

    def _gen(*a, **k):
        seen["laeufe"] += 1
        return [{"front": "a", "back": "A", "_section": 1}], "T"

    monkeypatch.setattr(mod, "generate_mc_from_source", _gen)
    return mod, seen, monkeypatch


def _ctx_with(n_sections: int):
    class _Ctx:
        sections = {i: f"q{i}.pdf" for i in range(1, n_sections + 1)}
        source_by_name = {f"q{i}.pdf": {"id": i, "uuid": f"u{i}"}
                          for i in range(1, n_sections + 1)}
    return _Ctx()


def _run(mod, monkeypatch, n_sections, count):
    monkeypatch.setattr(mod, "build_source_context", lambda *a, **k: _ctx_with(n_sections))
    run_generate_exercise_set(1, 7, "quiz", "source", count, source_uuids=["u-1"])


def test_the_top_up_is_checked_when_the_quota_fits(stack):
    mod, seen, monkeypatch = stack
    _run(mod, monkeypatch, n_sections=3, count=9)
    assert seen["gefragt"] == 1


def test_the_top_up_stays_away_with_more_sections_than_entries(stack):
    # 25 sources and 2 exercises: no section was ever promised anything.
    mod, seen, monkeypatch = stack
    _run(mod, monkeypatch, n_sections=25, count=2)
    assert seen["gefragt"] == 0


def test_a_single_section_needs_no_top_up(stack):
    mod, seen, monkeypatch = stack
    _run(mod, monkeypatch, n_sections=1, count=5)
    assert seen["gefragt"] == 0
