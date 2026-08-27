"""A typed name becomes rule and pattern example, rejected when in doubt."""

import json
import types

import pytest

from src.services.aia_grammar_topic import (
    _PROMPT,
    TASK_KINDS,
    derive_task_lines,
    derive_topic,
    usable_label,
)


def _client(content):
    calls = []

    def create(model, messages, **kwargs):
        calls.append(messages)
        message = types.SimpleNamespace(content=content)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])

    return types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
    ), calls


_GOOD = json.dumps({
    "is_grammar": True,
    "rule": "Input: indicative present. Output: Konjunktiv II.",
    "examples": [{"before": "Er kommt morgen.", "after": "Er käme morgen."}],
})


def test_a_grammar_topic_yields_rule_and_example():
    client, _ = _client(_GOOD)
    out = derive_topic(client, "m", "Konjunktiv II", "de")
    assert out["rule"].startswith("Input:")
    assert out["examples"][0]["before"] == "Er kommt morgen."
    assert out["examples"][0]["after"] == "Er käme morgen."


def test_the_prompt_carries_the_typed_name_and_the_language():
    client, calls = _client(_GOOD)
    derive_topic(client, "m", "Konjunktiv II", "de")
    sent = " ".join(m["content"] for m in calls[0])
    assert "Konjunktiv II" in sent
    assert "German" in sent


def test_something_that_is_not_grammar_is_refused():
    # Inventing a subject topic would be worse than a refusal.
    client, _ = _client(json.dumps({"is_grammar": False, "rule": "", "examples": []}))
    assert derive_topic(client, "m", "Photosynthese", "de") is None


def test_an_example_that_changes_nothing_is_refused():
    """Before equals after means the model did not understand the reshaping."""
    client, _ = _client(json.dumps({
        "is_grammar": True, "rule": "r",
        "examples": [{"before": "Er kommt.", "after": "Er kommt!"}],
    }))
    assert derive_topic(client, "m", "Irgendwas", "de") is None


def test_an_answer_without_any_example_is_refused():
    client, _ = _client(json.dumps({"is_grammar": True, "rule": "r", "examples": []}))
    assert derive_topic(client, "m", "Konjunktiv II", "de") is None


def test_an_answer_without_a_rule_is_refused():
    client, _ = _client(json.dumps({
        "is_grammar": True, "rule": "  ",
        "examples": [{"before": "a b c.", "after": "c b a."}],
    }))
    assert derive_topic(client, "m", "Konjunktiv II", "de") is None


def test_unusable_json_is_refused_instead_of_crashing():
    client, _ = _client("kein json")
    assert derive_topic(client, "m", "Konjunktiv II", "de") is None


def test_a_provider_failure_is_not_confused_with_a_bad_topic():
    """A disruption has to propagate, an unusable answer stays None."""
    def create(**kwargs):
        raise RuntimeError("Model Not Loaded.")

    client = types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
    )
    with pytest.raises(RuntimeError):
        derive_topic(client, "m", "Konjunktiv II", "de")


def test_a_fenced_answer_is_still_parsed():
    client, _ = _client(f"```json\n{_GOOD}\n```")
    assert derive_topic(client, "m", "Konjunktiv II", "de") is not None


def test_only_the_first_example_is_kept():
    # The generator only reads the first pair.
    pairs = [{"before": f"Satz {i} hier.", "after": f"Umgeformt {i} hier."}
             for i in range(5)]
    client, _ = _client(json.dumps({"is_grammar": True, "rule": "r", "examples": pairs}))
    out = derive_topic(client, "m", "X", "de")
    assert out["examples"] == [{"before": "Satz 0 hier.", "after": "Umgeformt 0 hier."}]


# ─── The name suggestion ─────────────────────────────────────────────────────

def test_a_clean_name_comes_through():
    assert usable_label("Passiv Präsens") == "Passiv Präsens"


def test_surrounding_space_is_trimmed():
    assert usable_label("  Perfekt  ") == "Perfekt"


@pytest.mark.parametrize("value", [None, "", "   ", 42, ["Passiv"], {"a": 1}])
def test_nothing_usable_is_no_suggestion(value):
    """Empty is not an error, the suggestion is a convenience and no gatekeeper."""
    assert usable_label(value) == ""


def test_a_whole_paragraph_is_no_suggestion():
    # A paragraph instead of a name means the question was not understood.
    assert usable_label("x" * 61) == ""
    assert usable_label("x" * 60) == "x" * 60


def test_more_than_one_line_is_no_suggestion():
    assert usable_label("Passiv Präsens\nund noch etwas") == ""
    assert usable_label("Passiv Präsens\rund noch etwas") == ""


def test_the_suggested_name_comes_back():
    client, _ = _client(json.dumps({
        "is_grammar": True, "rule": "r", "label": "Passiv Präsens",
        "examples": [{"before": "Das Team schreibt den Bericht.",
                      "after": "Der Bericht wird vom Team geschrieben."}],
    }))
    assert derive_topic(client, "m", "passi", "de")["label"] == "Passiv Präsens"


def test_a_topic_without_a_suggested_name_is_still_created():
    """The name suggestion is a convenience and must not cost a topic."""
    client, _ = _client(_GOOD)
    out = derive_topic(client, "m", "Konjunktiv II", "de")
    assert out is not None
    assert out["label"] == ""


def test_an_unusable_suggested_name_does_not_cost_the_topic():
    client, _ = _client(json.dumps({
        "is_grammar": True, "rule": "r", "label": "x" * 200,
        "examples": [{"before": "Er kommt morgen.", "after": "Er käme morgen."}],
    }))
    out = derive_topic(client, "m", "Konjunktiv II", "de")
    assert out is not None
    assert out["label"] == ""


def test_the_prompt_asks_for_the_suggested_name():
    client, calls = _client(_GOOD)
    derive_topic(client, "m", "Konjunktiv II", "de")
    sent = " ".join(m["content"] for m in calls[0])
    assert "label" in sent


def test_a_broken_pair_is_dropped_but_the_good_ones_stay():
    client, _ = _client(json.dumps({
        "is_grammar": True, "rule": "r",
        "examples": [
            {"before": "", "after": "x"},
            {"before": "Er kommt morgen.", "after": "Er käme morgen."},
        ],
    }))
    out = derive_topic(client, "m", "Konjunktiv II", "de")
    assert len(out["examples"]) == 1
    assert out["examples"][0]["before"] == "Er kommt morgen."


# Topics from before the field get their lines backfilled.

_MIT_ZEILEN = json.dumps({
    "is_grammar": True,
    "rule": "Input: two sentences. Output: one with a relative clause.",
    "examples": [{"before": "Der Mann ist Lehrer.", "after": "Der Mann, der Lehrer ist."}],
    "task_lines": {
        "transform": "Forme den Satz nach dem Beispiel in einen Relativsatz um.",
        "cloze": "Ergänze das fehlende Relativpronomen.",
        "statement": "Ist der Relativsatz richtig gebildet?",
        "choice": "Welcher Relativsatz ist richtig gebildet?",
    },
})


def test_the_lines_can_be_fetched_on_their_own():
    client, _ = _client(_MIT_ZEILEN)
    zeilen = derive_task_lines(client, "m", "Relativsatz", "de")
    assert zeilen["transform"] == "Forme den Satz nach dem Beispiel in einen Relativsatz um."
    assert set(zeilen) == set(TASK_KINDS)


def test_the_backfill_never_hands_back_rule_or_example():
    """Only the four lines come back, rule and pattern stay untouched."""
    client, _ = _client(_MIT_ZEILEN)
    assert set(derive_task_lines(client, "m", "Relativsatz", "de")) == set(TASK_KINDS)


def test_a_provider_hiccup_costs_the_lines_and_not_the_set():
    """When backfilling, a disruption must not cost a whole set."""
    def create(model, messages, **kwargs):
        raise RuntimeError("Model Not Loaded")

    client = types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create)))
    assert derive_task_lines(client, "m", "Relativsatz", "de") == {}


def test_a_topic_the_model_refuses_yields_no_lines():
    client, _ = _client(json.dumps({"is_grammar": False, "rule": "", "examples": []}))
    assert derive_task_lines(client, "m", "Photosynthese", "de") == {}


def test_a_word_order_mnemonic_counts_as_grammar():
    """The question is whether the name says something about sentence structure, not whether the model knows it."""
    assert "tekamolo" in _PROMPT
    assert "not automatically nonsense" in _PROMPT
    # Subject topics still drop out, otherwise the loosening would be a free pass.
    assert "photosynthesis" in _PROMPT
