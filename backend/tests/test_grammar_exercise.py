"""Grammar exercise: generation and checking, without database and network."""

import json
import types

import pytest

from src.features.ai_assistant.tasks.language_training._context import QuelleContext
from src.features.ai_assistant.tasks.language_training._source_grammar import (
    generate_grammar_from_source,
    is_usable_pair,
)
from src.services import aia_grammar_check as gc


MARKER = "\n\nADAPT-MARKER: pitch this at level A1."

# A grammar topic in the shape that comes from the database.
_TEXT_TYPE = {
    "id": 1,
    "label": "Passiv Präsens",
    "rule": "Input: an active sentence in the present tense. Output: the same statement "
            "in the passive voice, present tense.",
    "example": {"before": "Hilde erklärt einen komplizierten Begriff.",
                "after": "Ein komplizierter Begriff wird von Hilde erklärt."},
    "examples": [{"before": "Hilde erklärt einen komplizierten Begriff.",
                  "after": "Ein komplizierter Begriff wird von Hilde erklärt."}],
}


def _make_client(content):
    """Minimal OpenAI-client stand-in: records every call, always returns ``content``."""
    calls = []

    def create(model, messages, **kwargs):
        calls.append(messages)
        message = types.SimpleNamespace(content=content)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])

    return types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
    ), calls


def _system_of(calls):
    return calls[0][0]["content"]


def _ctx():
    return QuelleContext(
        context="[A.pdf, S. 4] Der Server speichert die Messwerte.",
        first_label="A.pdf",
        multi_label="A.pdf",
        source_hint="folgender Source",
        source_by_name={"A.pdf": {"id": 1, "workspace_id": 7}},
        seen_pages_by_source={1: {4}},
    )


# ─── Generierung ──────────────────────────────────────────────────────────────

_RESPONSE = json.dumps({
    "title": "Passiv im Datenmanagement",
    "example": {"before": "Hilde erklärt einen Begriff.", "after": "Ein Begriff wird von Hilde erklärt."},
    "exercises": [
        {"before": "Der Server speichert die Messwerte.",
         "after": "Die Messwerte werden vom Server gespeichert.",
         "explanation": "werden + Partizip II."},
        {"before": "Die Software prüft die Eingaben.",
         "after": "Die Eingaben werden von der Software geprüft.",
         "explanation": ""},
    ],
})


@pytest.fixture
def attributed(monkeypatch):
    """Records what was passed to the attribution, without pgvector."""
    seen: dict = {}

    def fake_attach(items, claims, ctx, **kwargs):
        seen["claims"] = list(claims)
        seen["items"] = [dict(i) for i in items]
        return items

    monkeypatch.setattr(
        "src.features.ai_assistant.tasks.language_training._source_grammar.attach_chips_cited",
        fake_attach,
    )
    return seen


def _generate(response=_RESPONSE, count=2, adaptive_suffix=""):
    client, calls = _make_client(response)
    items, title, header = generate_grammar_from_source(
        client, "m", _ctx(), _TEXT_TYPE, count, locale="de",
        adaptive_suffix=adaptive_suffix,
    )
    return items, title, header, calls


def test_generation_builds_items_and_a_title(attributed):
    items, title, header, _ = _generate()
    assert title == "Passiv im Datenmanagement"
    # No set header any more, the pattern hangs on the exercise.
    assert header == {}
    # Every exercise carries its instruction up front.
    assert [i["front"].split("\n\n")[-1] for i in items] == [
        "Der Server speichert die Messwerte.",
        "Die Software prüft die Eingaben.",
    ]
    assert items[0]["back"] == "Die Messwerte werden vom Server gespeichert."
    assert items[0]["explanation"] == "werden + Partizip II."
    # Empty explanation becomes None rather than an empty string in the DB.
    assert items[1]["explanation"] is None


def test_attribution_gets_the_transformed_sentences_as_claims(attributed):
    # The solution carries the source content, so it is what gets attributed.
    _generate()
    assert attributed["claims"] == [
        "Die Messwerte werden vom Server gespeichert.",
        "Die Eingaben werden von der Software geprüft.",
    ]


def test_generation_prompt_asks_the_model_where_it_took_the_material_from(attributed):
    """The model knows the passage and only has to name its number."""
    _, _, _, calls = _generate()
    system = _system_of(calls)
    assert '"page"' in system
    assert "S. " in system


def test_items_carry_the_page_the_model_cited(attributed):
    response = json.dumps({
        "title": "T",
        "example": {"before": "a b c.", "after": "c b a."},
        "exercises": [
            {"before": _GOOD[0], "after": _GOOD[1], "page": 4},
            {"before": _GOOD2[0], "after": _GOOD2[1]},
        ],
    })
    _generate(response, count=2)
    assert [i.get("_page") for i in attributed["items"]] == [4, None]


def test_generated_items_carry_no_multiple_choice_fields(attributed):
    # The answer is free text, so nothing must set options/correct_idx.
    items, _, _, _ = _generate()
    for item in items:
        assert "options" not in item
        assert "correct_idx" not in item


def test_generation_respects_the_requested_count(attributed):
    items, _, _, _ = _generate(count=1)
    assert len(items) == 1


def _exercises(*pairs):
    return json.dumps({
        "title": "T",
        "example": {"before": "Hilde erklärt einen Begriff.", "after": "Ein Begriff wird erklärt."},
        "exercises": [{"before": b, "after": a} for b, a in pairs],
    })


_GOOD = ("Der Server speichert die Messwerte.", "Die Messwerte werden vom Server gespeichert.")
_GOOD2 = ("Die Software prüft die Eingaben.", "Die Eingaben werden von der Software geprüft.")
_GOOD3 = ("Das Labor erhebt die Daten.", "Die Daten werden vom Labor erhoben.")


def test_generation_drops_unusable_pairs_but_keeps_the_run(attributed):
    response = _exercises(_GOOD, _GOOD2, _GOOD3, ("Was bedeutet Normalisierung?", "Egal."))
    items, _, _, _ = _generate(response, count=4)
    assert [i["front"].split("\n\n")[-1] for i in items] == [_GOOD[0], _GOOD2[0], _GOOD3[0]]


def test_generation_is_discarded_when_too_many_sentences_are_unusable(attributed):
    """Too many comprehension questions have to fail the set."""
    response = _exercises(
        _GOOD,
        ("Was bedeutet wissenschaftliches Arbeiten in einfachen Worten?", "Egal."),
        ("Nennen Sie drei Beispiele für Quellen?", "Egal."),
        ("Wie funktioniert das Zitieren?", "Egal."),
    )
    items, title, header, _ = _generate(response, count=4)
    assert items == []
    assert title == ""
    assert header == {}


@pytest.mark.parametrize("before, after", [
    ("Was bedeutet wissenschaftliches Arbeiten?", "Irgendwas."),   # question
    ("Der Server speichert die Daten.", "Und wer speichert sie?"),  # answer is a question
    ("Der Server speichert die Daten.", "Der Server speichert die Daten."),  # unchanged
    ("Der Server speichert die Daten.", "der server  speichert die daten!"),  # unchanged bar noise
    ("Wissenschaftliches Arbeiten", "Etwas."),                      # heading, not a sentence
    ("", "Etwas."),
    ("Der Server speichert die Daten.", ""),
])
def test_is_usable_pair_rejects_what_a_learner_cannot_solve(before, after):
    assert not is_usable_pair(before, after)


def test_is_usable_pair_accepts_a_proper_transformation():
    assert is_usable_pair(*_GOOD)


def test_is_usable_pair_rejects_a_question_in_any_script():
    # No German word list anywhere, so other question marks must work too.
    assert not is_usable_pair("¿Qué significa la normalización?", "Algo.")
    assert not is_usable_pair("النص العلمي ما هو؟", "شيء.")


def test_generation_prompt_carries_label_rule_and_adaptive_suffix(attributed):
    _, _, _, calls = _generate(adaptive_suffix=MARKER)
    system = _system_of(calls)
    # The instruction to the learner names no form and stays out.
    assert _TEXT_TYPE["label"] in system
    assert _TEXT_TYPE["rule"] in system
    assert MARKER in system
    # The whole point of the tool: sentences are written fresh from the source.
    assert "NEW" in system


def test_generation_prompt_leaves_difficulty_to_the_level_alone(attributed):
    """The difficulty comes from the language level alone."""
    _, _, _, calls = _generate()
    system = _system_of(calls)
    assert "14 words" not in system
    assert "under" not in system.split("SHAPE TO COPY")[0]
    # The shape rule stays: one sentence, not a paragraph.
    assert "exactly ONE sentence" in system


def test_generation_prompt_shows_the_worked_pair_as_a_shape_to_copy(attributed):
    # An example steers the format, a rule alone does not.
    _, _, _, calls = _generate()
    system = _system_of(calls)
    pair = _TEXT_TYPE["example"]
    assert "SHAPE TO COPY" in system
    assert pair["before"] in system
    assert pair["after"] in system
    # And it says outright what the wrong output looks like.
    assert "cannot be transformed" in system


def test_title_falls_back_to_the_type_label(attributed):
    response = json.dumps({
        "title": "",
        "example": {"before": "a", "after": "b"},
        "exercises": [{"before": b, "after": a} for b, a in (_GOOD, _GOOD2)],
    })
    _, title, _, _ = _generate(response, count=2)
    assert title == _TEXT_TYPE["label"]


def test_every_transform_carries_the_topics_worked_pattern(attributed):
    """Before a reshaping nobody may be left without a pattern."""
    response = json.dumps({
        "title": "T",
        "exercises": [{"before": b, "after": a} for b, a in (_GOOD, _GOOD2)],
    })
    items, _, _, _ = _generate(response, count=2)
    shipped = _TEXT_TYPE["example"]
    for item in items:
        assert item["extras"]["pattern_front"] == shipped["before"]
        assert item["extras"]["pattern_back"] == shipped["after"]


def test_a_transform_carries_the_other_valid_wordings(attributed):
    """They cost nothing at generation time and save every model-based check."""
    response = json.dumps({
        "title": "T",
        "exercises": [{
            "before": "Ich habe keine Zeit.",
            "after": "Ich hätte Zeit.",
            "also_ok": ["Ich würde Zeit haben.", "  ", "Ich habe keine Zeit."],
        }],
    })
    items, _, _, _ = _generate(response, count=1)
    # Empty ones out, and the unchanged template is not a solution.
    assert items[0]["extras"]["accepts"] == ["Ich würde Zeit haben."]


def test_a_transform_without_other_wordings_carries_none(attributed):
    response = json.dumps({
        "title": "T",
        "exercises": [{"before": _GOOD[0], "after": _GOOD[1]}],
    })
    items, _, _, _ = _generate(response, count=1)
    assert "accepts" not in items[0]["extras"]


def test_generation_asks_for_the_other_valid_wordings(attributed):
    _, _, _, calls = _generate()
    assert "also_ok" in _system_of(calls)


# ─── Checking: normalisation ─────────────────────────────────────────────────

@pytest.mark.parametrize("given", [
    "Die Messwerte werden vom Server gespeichert.",
    "die messwerte werden vom server gespeichert",
    "Die Messwerte werden vom Server gespeichert!",
    "Die  Messwerte   werden vom Server gespeichert .",
])
def test_exact_match_ignores_case_punctuation_and_spacing(given):
    assert gc.is_exact_match(given, "Die Messwerte werden vom Server gespeichert.")


def test_exact_match_ignores_optional_parenthetical_agent():
    # The worked example writes the agent in brackets, so leaving it out is right too.
    expected = "Die Briefe müssen (von mir) zur Post gebracht werden."
    assert gc.is_exact_match("Die Briefe müssen zur Post gebracht werden.", expected)


def test_exact_match_rejects_a_different_sentence():
    assert not gc.is_exact_match(
        "Der Server speichert die Messwerte.",
        "Die Messwerte werden vom Server gespeichert.",
    )


def test_empty_answer_is_never_an_exact_match():
    assert not gc.is_exact_match("", "irgendwas")
    assert not gc.is_exact_match("   ", "irgendwas")


def test_normalize_is_language_agnostic():
    # No word lists, punctuation is dropped by Unicode category.
    assert gc.normalize("¿Qué pasa?") == "qué pasa"
    assert gc.normalize("Der Grenzwert — laut Skript.") == "der grenzwert laut skript"


def test_overlap_ratio_bounds():
    assert gc.overlap_ratio("a b c", "a b c") == 1.0
    assert gc.overlap_ratio("", "a b") == 0.0
    assert 0 < gc.overlap_ratio("a b x", "a b c") < 1


def test_marking_a_near_miss_is_close_and_a_miss_is_wrong():
    expected = "Die Eingaben werden von der Software geprüft."
    assert gc.mark_answer(expected, expected) == gc.VERDICT_CORRECT
    # One wrong form, everything else identical.
    assert gc.mark_answer(
        "Die Eingaben werden von der Software prüfen.", expected) == gc.VERDICT_CLOSE
    assert gc.mark_answer("Keine Ahnung.", expected) == gc.VERDICT_WRONG


# ─── Checking: valid alternative versions ────────────────────────────────────

def test_an_accepted_wording_counts_as_correct():
    # Without a delivered alternative an equally correct form fails.
    expected = "Das Smartphone wäre ein Zeitfresser."
    variant = "Das Smartphone würde ein Zeitfresser sein."
    assert gc.mark_answer(variant, expected, [variant]) == gc.VERDICT_CORRECT
    assert gc.mark_answer(variant, expected) != gc.VERDICT_CORRECT


def test_close_is_measured_against_the_nearest_wording():
    expected = "Das Smartphone wäre ein Zeitfresser."
    variant = "Das Smartphone würde ein Zeitfresser sein."
    # Measured against the model solution it would be far off, against the alternative it is close.
    assert gc.mark_answer(
        "Das Smartphone würde ein Zeitfresser seien.", expected, [variant]
    ) == gc.VERDICT_CLOSE


def test_the_check_module_has_no_model_client_at_all():
    """The check is a pure comparison, one call per answer would be the costliest way."""
    assert not hasattr(gc, "check_answer")
    assert not hasattr(gc, "get_check_client")
