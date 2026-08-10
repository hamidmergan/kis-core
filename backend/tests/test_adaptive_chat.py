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


def test_default_behavior_is_style_only_and_covers_the_bands():
    """The default steers WORDING and must give a rule for every band A1..C2.

    What it must NOT do is hand the model a role. It used to open with "ADAPT TO
    THE LEARNER" and claim to OVERRIDE the rules above, and that read as "you are
    this learner's language tutor": measured 2026-07-29, a grammar question no
    document answered got a full invented lesson with the trainer on and the
    correct refusal with it off. A role beats a single prohibition sentence, so
    the text stays a style rule with an explicit carve-out for the refusal.
    """
    b = DEFAULT_ADAPTIVE_BEHAVIOR
    assert "STYLE" in b
    assert "no role" in b
    assert "never decides" in b.lower()
    # The refusal is one sentence at every level — the "never shorter" rule above
    # it must not be allowed to inflate it back into an answer.
    assert "not-in-sources sentence" in b
    # Grammar stays out of the model's remit unless a document states it.
    assert "language teacher" in b
    # Die Stufen kommen aus der Stufen-Leiter, der Text nennt sie nur noch ueber
    # den Platzhalter. Die eigene A1/A2..C1/C2-Liste ist bewusst raus.
    from src.services.aia_adaptive_chat import DESCRIPTION_PLACEHOLDER
    assert DESCRIPTION_PLACEHOLDER in b
    assert "C1 or C2" in b
    # Consistent informal address, so it does not flip between du and Sie.
    assert '"du"' in b and '"Sie"' in b


def test_default_behavior_never_drops_facts_at_the_low_levels():
    """Simplifying is about WORDING, never about leaving content out.

    Regression: with a learner on A2 the same question lost the Peer-Review, the
    Extended Abstract, the grading relevance and the access route that the same
    workspace answered in full with adaptation off. The A1/A2 branch told the
    model to give "only the few MOST important points, not everything" and to
    "keep the whole answer short", and the header let the block override the base
    prompt's completeness rule.
    """
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
    """A2 collapsed a structured answer into one prose block.

    The base prompt's RESPONSE STRUCTURE rules (headings, bullets, tables) apply
    at every level, so the block has to say it does not override them.
    """
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
    """The guard must end the suffix, after the behaviour text.

    The suffix is appended at the END of the user message, so the tail is what the
    model weights most. When the guard stopped being last, the adaptive block's
    "never shorter" won and the chat answered off-topic messages instead of
    refusing (regression seen 2026-07-29).
    """
    from src.services.aia_adaptive_chat import seal_adaptive_suffix, ADAPTIVE_SOURCES_GUARD
    sealed = seal_adaptive_suffix("\n\nBEHAVIOUR TEXT")
    assert sealed.endswith(ADAPTIVE_SOURCES_GUARD)
    assert "BEHAVIOUR TEXT" in sealed


def test_guard_holds_without_an_adaptive_block():
    """The sources rule does not depend on the Fachsprachentrainer being on.

    It used to be skipped without an adaptive block, on the theory that the system
    prompt refuses on its own. It does not: with the trainer off the tutor still
    invented a grammar lesson its sources never contained (2026-07-29)."""
    from src.services.aia_adaptive_chat import seal_adaptive_suffix, ADAPTIVE_SOURCES_GUARD
    assert seal_adaptive_suffix("").endswith(ADAPTIVE_SOURCES_GUARD)


def test_sources_guard_cannot_be_deleted_by_an_admin_edit():
    """The guard lives in code, NOT in the admin-editable behaviour text: an expert
    rewriting the didactics in the admin UI must not be able to remove the rule that
    keeps the chat from inventing answers."""
    from src.services.aia_adaptive_chat import ADAPTIVE_SOURCES_GUARD, DEFAULT_ADAPTIVE_BEHAVIOR
    assert ADAPTIVE_SOURCES_GUARD not in DEFAULT_ADAPTIVE_BEHAVIOR


# ─── Stufen-Leiter: die Beschreibung kommt aus der Karte ─────────────────────

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
    """Die Stufen stehen in der Karte, nicht mehr doppelt im Verhaltenstext."""
    b = DEFAULT_ADAPTIVE_BEHAVIOR
    assert "- A1 or A2:" not in b
    assert "- B1:" not in b
    assert "- B2:" not in b
    assert "- C1 or C2:" not in b


def test_default_behavior_keeps_the_glossing_instruction():
    """Der Auftrag zum Erklaeren von Fachwoertern darf nicht mit der Liste verschwinden."""
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
