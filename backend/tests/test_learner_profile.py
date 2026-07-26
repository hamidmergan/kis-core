"""Pure unit tests for the learner-profile weighting and appendix logic."""
from datetime import datetime, timedelta, timezone

from src.services.aia_learner_profile import (
    BASE_WEIGHTS, ACT_THRESHOLD, PROFILE_CAP, DEFAULT_WINDOW_DAYS,
    CATEGORY_TERM, CATEGORY_TOOL,
    normalize_key, base_weight, effective_weight, accumulate, graduate,
    select_focus, weakness_focus_appendix, overflow_ids,
)

NOW = datetime(2026, 7, 26, 12, 0, tzinfo=timezone.utc)


def test_normalize_key_lowercases_and_collapses_whitespace():
    assert normalize_key("  Der   Konjunktiv ") == "der konjunktiv"


def test_normalize_key_truncates_long_labels():
    assert len(normalize_key("x" * 500)) == 200


def test_base_weight_known_and_unknown():
    assert base_weight("quiz_wrong") == 3.0
    assert base_weight("something_new") == 1.0  # sensible default


def test_effective_weight_full_at_age_zero():
    assert effective_weight(6.0, NOW, NOW, 30) == 6.0


def test_effective_weight_zero_at_or_past_window():
    old = NOW - timedelta(days=30)
    assert effective_weight(6.0, old, NOW, 30) == 0.0


def test_effective_weight_linear_midpoint():
    mid = NOW - timedelta(days=15)
    assert effective_weight(6.0, mid, NOW, 30) == 3.0


def test_accumulate_adds_base_weight():
    assert accumulate(4.0, "quiz_hint") == 6.0


def test_graduate_shrinks_weight():
    assert graduate(6.0) == 6.0 * 0.3


def test_select_focus_filters_below_threshold_sorts_and_caps():
    items = [
        {"label": "weak_a", "weight": 6.0, "last_seen_at": NOW, "category": CATEGORY_TERM},
        {"label": "weak_b", "weight": 9.0, "last_seen_at": NOW, "category": CATEGORY_TERM},
        {"label": "quiet", "weight": 2.0, "last_seen_at": NOW, "category": CATEGORY_TERM},
    ]
    focus = select_focus(items, NOW, DEFAULT_WINDOW_DAYS, top_n=5)
    labels = [f["label"] for f in focus]
    assert labels == ["weak_b", "weak_a"]  # over-threshold, strongest first
    assert "quiet" not in labels


def test_select_focus_ignores_tool_category():
    items = [{"label": "mindmap", "weight": 9.0, "last_seen_at": NOW, "category": CATEGORY_TOOL}]
    assert select_focus(items, NOW, DEFAULT_WINDOW_DAYS) == []


def test_weakness_appendix_empty_without_labels():
    assert weakness_focus_appendix([]) == ""


def test_weakness_appendix_lists_terms_and_stays_subtle():
    text = weakness_focus_appendix(["Konjunktiv", "Passiv"])
    assert "Konjunktiv" in text and "Passiv" in text
    assert text.startswith("\n\n")
    assert "subtle" in text.lower()


def test_overflow_ids_empty_under_cap():
    items = [{"id": i, "weight": 5.0, "last_seen_at": NOW} for i in range(PROFILE_CAP)]
    assert overflow_ids(items, NOW, DEFAULT_WINDOW_DAYS) == []


def test_overflow_ids_evicts_weakest_over_cap():
    items = [{"id": i, "weight": float(i + 1), "last_seen_at": NOW} for i in range(PROFILE_CAP + 2)]
    # two weakest ids (0 and 1) must be evicted
    assert set(overflow_ids(items, NOW, DEFAULT_WINDOW_DAYS)) == {0, 1}
