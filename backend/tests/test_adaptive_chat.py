"""Tests for the adaptive tutor prompt appendix."""

from src.services.aia_adaptive_chat import adaptive_chat_appendix, DEFAULT_ADAPTIVE_BEHAVIOR
from src.features.ai_assistant.prompts.rag_chat import aia_system_rag


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
    assert combined.startswith("## Role\nYou are an AI tutor")
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


def test_default_behavior_is_style_only_and_covers_the_bands():
    """The default steers the wording and prescribes no role."""
    b = DEFAULT_ADAPTIVE_BEHAVIOR
    assert "STYLE" in b
    assert "no role" in b
    assert "never decides" in b.lower()
    # The refusal stays one sentence at every level.
    assert "not-in-sources sentence" in b
    # Grammar stays out of the model's remit unless a document states it.
    assert "language teacher" in b
    # The levels come from the ladder, the text only names the placeholder.
    from src.services.aia_adaptive_chat import DESCRIPTION_PLACEHOLDER
    assert DESCRIPTION_PLACEHOLDER in b
    assert "C1 or C2" in b
    # Consistent informal address, so it does not flip between du and Sie.
    assert '"du"' in b and '"Sie"' in b


def test_default_behavior_does_not_turn_a_word_question_into_a_grammar_question():
    """Asking what a term means is an ordinary question."""
    b = DEFAULT_ADAPTIVE_BEHAVIOR
    assert "the quoted words are not the answer" not in b
    assert "quotes words which do appear" not in b
    # What the paragraph is actually for stays untouched.
    assert "language teacher" in b
    assert "not-in-sources sentence" in b


def test_default_behavior_never_drops_facts_at_the_low_levels():
    """Simplifying concerns the wording, never the content."""
    b = DEFAULT_ADAPTIVE_BEHAVIOR
    low = b.lower()
    assert "not everything" not in low
    assert "most important points" not in low
    assert "keep the whole answer short" not in low
    # Completeness is the base prompt's business, this block must not claim it.
    assert "completeness" not in low
    # And it says so positively, the way the tool variant already does.
    assert "never leave a fact out" in low


def test_default_behavior_keeps_the_response_structure_at_the_low_levels():
    """The level block must not override the structuring rules of the main prompt."""
    low = DEFAULT_ADAPTIVE_BEHAVIOR.lower()
    assert "response structure" in low


def test_example_for_level_picks_the_matching_band():
    from src.services.aia_adaptive_chat import example_for_level
    examples = {"A1": "eins", "A2": "zwei", "B1": "drei", "B2": "vier"}
    assert example_for_level("A1", examples) == "eins"
    assert example_for_level("B1", examples) == "drei"


def test_example_for_level_covers_the_upper_bands():
    from src.services.aia_adaptive_chat import example_for_level
    examples = {"A1": "eins", "B2": "vier", "C1": "fuenf", "C2": "sechs"}
    assert example_for_level("B2", examples) == "vier"
    assert example_for_level("C1", examples) == "fuenf"
    assert example_for_level("C2", examples) == "sechs"


def test_example_for_level_empty_when_band_has_no_example():
    from src.services.aia_adaptive_chat import example_for_level
    assert example_for_level("C2", {"A1": "eins"}) == ""


def test_example_for_level_joins_multiple_examples():
    from src.services.aia_adaptive_chat import example_for_level
    assert example_for_level("A1", {"A1": "-- Satz eins. -- Satz zwei."}) == "Satz eins. / Satz zwei."


def test_example_for_level_empty_without_level():
    from src.services.aia_adaptive_chat import example_for_level
    assert example_for_level(None, {"A1": "eins"}) == ""


def test_sources_guard_is_the_last_thing_the_model_reads():
    """The source guard has to end the suffix, the end weighs the most."""
    from src.services.aia_adaptive_chat import seal_adaptive_suffix, ADAPTIVE_SOURCES_GUARD
    sealed = seal_adaptive_suffix("\n\nBEHAVIOUR TEXT")
    assert sealed.endswith(ADAPTIVE_SOURCES_GUARD)
    assert "BEHAVIOUR TEXT" in sealed




def test_sources_guard_cannot_be_deleted_by_an_admin_edit():
    """The guard lives in the code, not in the admin text."""
    from src.services.aia_adaptive_chat import ADAPTIVE_SOURCES_GUARD, DEFAULT_ADAPTIVE_BEHAVIOR
    assert ADAPTIVE_SOURCES_GUARD not in DEFAULT_ADAPTIVE_BEHAVIOR


# ─── Level ladder: the description comes from the ladder ─────────────────────

def test_appendix_substitutes_the_description():
    from src.services.aia_adaptive_chat import adaptive_chat_appendix
    suffix, applied = adaptive_chat_appendix(
        "B1", "Stufe {level}: {description}", "", "Nebensaetze gehen."
    )
    assert "Stufe B1: Nebensaetze gehen." in suffix
    assert applied == "B1"


def test_appendix_leaves_no_placeholder_when_the_description_is_empty():
    from src.services.aia_adaptive_chat import adaptive_chat_appendix
    suffix, _ = adaptive_chat_appendix("B1", "Stufe {level}: {description}.", "", "")
    assert "{description}" not in suffix


def test_default_behavior_carries_the_description_placeholder():
    from src.services.aia_adaptive_chat import DESCRIPTION_PLACEHOLDER
    assert DESCRIPTION_PLACEHOLDER in DEFAULT_ADAPTIVE_BEHAVIOR


def test_default_behavior_no_longer_carries_its_own_band_list():
    """The levels live in the ladder, no longer duplicated in the behaviour text."""
    b = DEFAULT_ADAPTIVE_BEHAVIOR
    assert "- A1 or A2:" not in b
    assert "- B1:" not in b
    assert "- B2:" not in b
    assert "- C1 or C2:" not in b


def test_default_behavior_keeps_the_glossing_instruction():
    """The instruction to explain technical terms must not vanish with the list."""
    low = DEFAULT_ADAPTIVE_BEHAVIOR.lower()
    assert "gloss" in low
    assert "from the documents" in low


def test_level_texts_reads_both_settings(monkeypatch):
    import src.database as db
    from src.services.aia_adaptive_chat import level_texts

    store = {
        "language_diagnosis_level_examples_de": '{"B1": "Ein B1-Satz."}',
        "language_diagnosis_level_descriptions_de": '{"B1": "Nebensaetze gehen."}',
    }
    monkeypatch.setattr(db, "get_setting", lambda key, default="": store.get(key, default))
    example, description = level_texts("B1")
    assert example == "Ein B1-Satz."
    assert description == "Nebensaetze gehen."


def test_level_texts_without_a_level_is_empty():
    from src.services.aia_adaptive_chat import level_texts
    assert level_texts(None) == ("", "")
