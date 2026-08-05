"""Grammatik-Übung: Generierung und Prüfung.

Kein DB- und kein Netzzugriff. Der Generator bekommt einen Fake-Client, die
Attribution wird ausgehängt (sie hat eigene Tests in test_aia_tool_attribution).
"""

import json
import types

import pytest

from src.features.ai_assistant.tasks.language_training._context import QuelleContext
from src.features.ai_assistant.tasks.language_training._source_grammar import (
    _INSTRUCTION,
    generate_grammar_from_source,
    is_usable_pair,
)
from src.services import aia_grammar_check as gc


MARKER = "\n\nADAPT-MARKER: pitch this at level A1."

# Ein Grammatikthema in der Form, die die Generierung aus der Datenbank baut. Früher
# stand dieses dict im Code-Katalog, die Form ist absichtlich dieselbe geblieben, damit
# sich an den Generatoren keine Zeile ändern musste.
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
    """Record what attribution was asked for, without touching pgvector.

    The chip wiring itself is covered by test_grammar_citation; here only what the
    grammar generator hands over matters.
    """
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
    # Kein Set-Kopf mehr: ein gemischtes Set hat kein gemeinsames Muster, das über
    # allem stehen könnte. Es hängt an der Aufgabe, die eines braucht.
    assert header == {}
    assert [i["front"] for i in items] == [
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
    """The sentences are invented, so searching them back afterwards fails often. The
    model itself knows the passage it used, and every context line is labelled with a
    page, so it only has to name that number."""
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
    assert [i["front"] for i in items] == [_GOOD[0], _GOOD2[0], _GOOD3[0]]


def test_generation_is_discarded_when_too_many_sentences_are_unusable(attributed):
    """The reported bug: the model returns comprehension questions, which cannot be
    transformed. Half broken must fail the set rather than reach the learner."""
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
    # The label names the target form. The learner-facing instruction does not, it
    # only points at the worked pair, so it is deliberately kept out of the prompt.
    assert _TEXT_TYPE["label"] in system
    assert _INSTRUCTION["de"] not in system
    assert _TEXT_TYPE["rule"] in system
    assert MARKER in system
    # The whole point of the tool: sentences are written fresh from the source.
    assert "NEW" in system


def test_generation_prompt_leaves_difficulty_to_the_level_alone(attributed):
    """Sentence difficulty has exactly one source, the learner's CEFR level. A length
    cap in this prompt would contradict the adaptive block at B2 and above, which
    tells the model not to simplify."""
    _, _, _, calls = _generate()
    system = _system_of(calls)
    assert "14 words" not in system
    assert "under" not in system.split("SHAPE TO COPY")[0]
    # The shape rule stays: one sentence, not a paragraph.
    assert "exactly ONE sentence" in system


def test_generation_prompt_shows_the_worked_pair_as_a_shape_to_copy(attributed):
    # Rules alone get ignored by the chat model, an example is what actually steers
    # the format (same lesson as the overview prose fix).
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
    """Vor einer Umformung darf niemand ohne Muster stehen. Es kommt jetzt vom Thema
    und hängt an der Aufgabe, statt einmal über dem ganzen Set zu stehen."""
    response = json.dumps({
        "title": "T",
        "exercises": [{"before": b, "after": a} for b, a in (_GOOD, _GOOD2)],
    })
    items, _, _, _ = _generate(response, count=2)
    shipped = _TEXT_TYPE["example"]
    for item in items:
        assert item["extras"]["pattern_front"] == shipped["before"]
        assert item["extras"]["pattern_back"] == shipped["after"]


# ─── Prüfung: Normalisierung ─────────────────────────────────────────────────

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
    # No German word list anywhere: punctuation is stripped by Unicode category,
    # so other languages and scripts behave the same.
    assert gc.normalize("¿Qué pasa?") == "qué pasa"
    assert gc.normalize("Der Grenzwert — laut Skript.") == "der grenzwert laut skript"


def test_overlap_ratio_bounds():
    assert gc.overlap_ratio("a b c", "a b c") == 1.0
    assert gc.overlap_ratio("", "a b") == 0.0
    assert 0 < gc.overlap_ratio("a b x", "a b c") < 1


def test_heuristic_marks_a_near_miss_close_and_a_miss_wrong():
    expected = "Die Eingaben werden von der Software geprüft."
    assert gc.heuristic_verdict(expected, expected) == gc.VERDICT_CORRECT
    # One wrong form, everything else identical.
    assert gc.heuristic_verdict(
        "Die Eingaben werden von der Software prüfen.", expected) == gc.VERDICT_CLOSE
    assert gc.heuristic_verdict("Keine Ahnung.", expected) == gc.VERDICT_WRONG


# ─── Prüfung: Modell-Aufruf ──────────────────────────────────────────────────

def test_exact_answer_is_marked_without_any_model_call():
    """The reason the two-stage check exists: the provider rate limit is shared
    across the university, so a right answer must not cost a call."""
    client, calls = _make_client("should never be used")
    out = gc.check_answer(
        client, "m",
        given="Die Messwerte werden vom Server gespeichert.",
        expected="Die Messwerte werden vom Server gespeichert.",
        prompt_sentence="Der Server speichert die Messwerte.",
        rule="r",
    )
    assert out == {"verdict": "correct", "feedback": None, "used_llm": False}
    assert calls == []


def test_deviating_answer_asks_the_model_and_returns_its_verdict():
    client, calls = _make_client(json.dumps({"verdict": "close", "feedback": "Partizip fehlt."}))
    out = gc.check_answer(
        client, "m",
        given="Die Messwerte werden vom Server speichern.",
        expected="Die Messwerte werden vom Server gespeichert.",
        prompt_sentence="Der Server speichert die Messwerte.",
        rule="RULE-MARKER",
        language="German",
    )
    assert out["verdict"] == "close"
    assert out["feedback"] == "Partizip fehlt."
    assert out["used_llm"] is True
    system = _system_of(calls)
    assert "RULE-MARKER" in system
    assert "German" in system
    # The learner must not be handed the solution inside the feedback text.
    assert "Never reveal the expected solution" in system


def test_model_answer_in_a_code_fence_is_still_parsed():
    fenced = "```json\n{\"verdict\": \"wrong\", \"feedback\": \"Falsche Zeit.\"}\n```"
    client, _ = _make_client(fenced)
    out = gc.check_answer(
        client, "m", given="x", expected="y", prompt_sentence="z", rule="r")
    assert out["verdict"] == "wrong"


def test_unknown_verdict_falls_back_to_the_heuristic():
    client, _ = _make_client(json.dumps({"verdict": "vielleicht", "feedback": "hm"}))
    expected = "Die Eingaben werden von der Software geprüft."
    out = gc.check_answer(
        client, "m",
        given="Die Eingaben werden von der Software prüfen.",
        expected=expected, prompt_sentence="s", rule="r")
    assert out["verdict"] == gc.VERDICT_CLOSE
    assert out["used_llm"] is False
    assert out["feedback"] is None


def test_provider_error_falls_back_to_the_heuristic_instead_of_blocking():
    def create(**kwargs):
        raise RuntimeError("provider down")

    client = types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
    )
    out = gc.check_answer(
        client, "m",
        given="Völlig daneben.",
        expected="Die Eingaben werden von der Software geprüft.",
        prompt_sentence="s", rule="r")
    assert out["verdict"] == gc.VERDICT_WRONG
    assert out["used_llm"] is False
