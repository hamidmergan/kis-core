"""Pure unit tests for the learner-profile weighting and appendix logic."""
from datetime import datetime, timedelta, timezone

from src.services.aia_learner_profile import (
    BASE_WEIGHTS, ACT_THRESHOLD, PROFILE_CAP, DEFAULT_WINDOW_DAYS,
    CATEGORY_TERM, CATEGORY_PASSAGE, CATEGORY_TOOL,
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


def test_no_single_event_crosses_the_threshold():
    # The profile stays gentle: one event alone never reaches the act threshold, so
    # a single slip stays silent until it accumulates.
    assert all(w <= ACT_THRESHOLD for w in BASE_WEIGHTS.values())


def test_effective_weight_full_at_age_zero():
    assert effective_weight(6.0, NOW, NOW, 30) == 6.0


def test_effective_weight_zero_at_or_past_window():
    old = NOW - timedelta(days=30)
    assert effective_weight(6.0, old, NOW, 30) == 0.0


def test_effective_weight_linear_midpoint():
    mid = NOW - timedelta(days=15)
    assert effective_weight(6.0, mid, NOW, 30) == 3.0


def test_accumulate_adds_base_weight():
    assert accumulate(2.0, "quiz_wrong") == 5.0


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
    text = weakness_focus_appendix([
        {"label": "Konjunktiv", "category": CATEGORY_TERM},
        {"label": "Passiv", "category": CATEGORY_TERM},
    ])
    assert "Konjunktiv" in text and "Passiv" in text
    assert text.startswith("\n\n")
    assert "subtle" in text.lower()
    assert "terms" in text.lower()


def test_weakness_appendix_separates_passages_from_terms():
    # A whole question (passage) must be phrased as a topic to keep simple, not as a
    # term to define inline. Terms and passages appear in their own clauses.
    text = weakness_focus_appendix([
        {"label": "Konjunktiv", "category": CATEGORY_TERM},
        {"label": "Wie läuft eine wissenschaftliche Konferenz ab?", "category": CATEGORY_PASSAGE},
    ])
    assert "Konjunktiv" in text
    assert "Wie läuft eine wissenschaftliche Konferenz ab?" in text
    assert "questions or topics" in text.lower()  # the passage clause
    assert "these terms difficult" in text.lower()  # the term clause


def test_weakness_appendix_passage_only():
    text = weakness_focus_appendix([
        {"label": "Was ist Peer-Review?", "category": CATEGORY_PASSAGE},
    ])
    assert "Was ist Peer-Review?" in text
    assert "questions or topics" in text.lower()
    assert "these terms difficult" not in text.lower()  # no term clause when no terms


def test_passage_over_threshold_enters_focus():
    # A passage (e.g. accumulated translations of the same text) over the threshold
    # must reach the prompt, exactly like a term does.
    items = [{"label": "Wie funktioniert Zitieren?", "weight": 5.0,
              "last_seen_at": NOW, "category": CATEGORY_PASSAGE}]
    focus = select_focus(items, NOW, DEFAULT_WINDOW_DAYS)
    assert [f["label"] for f in focus] == ["Wie funktioniert Zitieren?"]


def test_overflow_ids_empty_under_cap():
    items = [{"id": i, "weight": 5.0, "last_seen_at": NOW} for i in range(PROFILE_CAP)]
    assert overflow_ids(items, NOW, DEFAULT_WINDOW_DAYS) == []


def test_overflow_ids_evicts_weakest_over_cap():
    items = [{"id": i, "weight": float(i + 1), "last_seen_at": NOW} for i in range(PROFILE_CAP + 2)]
    # two weakest ids (0 and 1) must be evicted
    assert set(overflow_ids(items, NOW, DEFAULT_WINDOW_DAYS)) == {0, 1}


def test_focus_survives_small_decay_at_trigger_sum():
    # Regression: a term accumulated to the wrong+hint sum (5.0) is read a moment
    # later, so its effective weight is a hair below 5.0 due to continuous decay.
    # It MUST still be in focus. (This is the exact bug live testing caught.)
    items = [{"label": "Konjunktiv", "weight": 5.0,
              "last_seen_at": NOW - timedelta(hours=1), "category": CATEGORY_TERM}]
    assert [f["label"] for f in select_focus(items, NOW, DEFAULT_WINDOW_DAYS)] == ["Konjunktiv"]


def test_wrong_plus_glossary_stays_below_threshold():
    # wrong(3.0)+glossary(1.0)=4.0 is below the 4.5 threshold and must stay quiet.
    items = [{"label": "Ellipse", "weight": 4.0, "last_seen_at": NOW, "category": CATEGORY_TERM}]
    assert select_focus(items, NOW, DEFAULT_WINDOW_DAYS) == []
