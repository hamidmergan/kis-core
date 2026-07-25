"""Tests for the adaptive tutor prompt appendix."""

from src.services.aia_adaptive_chat import adaptive_chat_appendix, DEFAULT_ADAPTIVE_BEHAVIOR
from src.tool_prompts import aia_system_rag


def test_no_level_means_no_change():
    suffix, applied = adaptive_chat_appendix(None, DEFAULT_ADAPTIVE_BEHAVIOR)
    assert suffix == ""
    assert applied is None


def test_empty_behavior_means_no_change():
    suffix, applied = adaptive_chat_appendix("A2", "   ")
    assert suffix == ""
    assert applied is None


def test_level_and_behavior_build_suffix():
    suffix, applied = adaptive_chat_appendix("A2", "Answer to match {level}.")
    assert applied == "A2"
    assert "A2" in suffix
    assert suffix.startswith("\n")


def test_suffix_appends_after_base_prompt():
    suffix, _ = adaptive_chat_appendix("A1", DEFAULT_ADAPTIVE_BEHAVIOR)
    combined = aia_system_rag("de") + suffix
    assert combined.startswith("You are an AI tutor")
    # The learner's level is substituted into the appendix.
    assert "level A1" in combined


def test_appendix_substitutes_level_and_example():
    suffix, applied = adaptive_chat_appendix("A2", "Level {level}. Sample: {example}", "Hallo.")
    assert applied == "A2"
    assert "Level A2. Sample: Hallo." in suffix
    assert "{level}" not in suffix and "{example}" not in suffix


def test_default_behavior_carries_both_placeholders():
    from src.services.aia_adaptive_chat import LEVEL_PLACEHOLDER, EXAMPLE_PLACEHOLDER
    assert LEVEL_PLACEHOLDER in DEFAULT_ADAPTIVE_BEHAVIOR
    assert EXAMPLE_PLACEHOLDER in DEFAULT_ADAPTIVE_BEHAVIOR


def test_default_behavior_overrides_and_covers_the_bands():
    """The default must be assertive enough to beat the RAG completeness rules,
    and it must give a rule for every band. Regression for the fix where the
    adaptation was present but did not visibly change the answer."""
    b = DEFAULT_ADAPTIVE_BEHAVIOR
    assert "OVERRIDES" in b
    assert "A1 or A2" in b
    assert "B1" in b
    assert "Above B1" in b
    # Consistent informal address, so it does not flip between du and Sie.
    assert '"du"' in b and '"Sie"' in b


def test_example_for_level_picks_the_matching_band():
    from src.services.aia_adaptive_chat import example_for_level
    examples = {"A1": "eins", "A2": "zwei", "B1": "drei", "B2": "vier"}
    assert example_for_level("A1", examples) == "eins"
    assert example_for_level("B1", examples) == "drei"


def test_example_for_level_borrows_b2_for_b1plus():
    from src.services.aia_adaptive_chat import example_for_level
    examples = {"A1": "eins", "A2": "zwei", "B1": "drei", "B2": "vier"}
    assert example_for_level("B1+", examples) == "vier"


def test_example_for_level_joins_multiple_examples():
    from src.services.aia_adaptive_chat import example_for_level
    assert example_for_level("A1", {"A1": "-- Satz eins. -- Satz zwei."}) == "Satz eins. / Satz zwei."


def test_example_for_level_empty_without_level():
    from src.services.aia_adaptive_chat import example_for_level
    assert example_for_level(None, {"A1": "eins"}) == ""
