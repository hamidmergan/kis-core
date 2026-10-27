"""A grammar set mixes four formats, as a number in the prompt instead of an intent."""

import json
import types

import pytest

from src.features.ai_assistant.tasks.language_training._context import QuelleContext
from src.features.ai_assistant.tasks.language_training._source_grammar import (
    KINDS,
    generate_grammar_from_source,
    is_usable_cloze,
    is_usable_pair,
    is_usable_statement,
    item_plan,
)


_TOPIC = {
    "id": 1,
    "label": "Passiv Präsens",
    "rule": "Input: an active sentence. Output: the same statement in the passive.",
    "example": {"before": "Hilde erklärt einen Begriff.",
                "after": "Ein Begriff wird von Hilde erklärt."},
    "examples": [{"before": "Hilde erklärt einen Begriff.",
                  "after": "Ein Begriff wird von Hilde erklärt."}],
}


def _client(content):
    calls = []

    def create(model, messages, **kwargs):
        calls.append(messages)
        message = types.SimpleNamespace(content=content)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])

    return types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
    ), calls


def _client_queue(*contents):
    """A stub client that returns the answers in order."""
    calls = []
    queue = list(contents)

    def create(model, messages, **kwargs):
        calls.append(messages)
        content = queue[min(len(calls) - 1, len(queue) - 1)]
        message = types.SimpleNamespace(content=content)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])

    return types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
    ), calls


def _ctx():
    return QuelleContext(
        context="[A.pdf, S. 4] Der Server speichert die Messwerte.",
        first_label="A.pdf", multi_label="A.pdf", source_hint="folgender Source",
        source_by_name={"A.pdf": {"id": 1, "workspace_id": 7}},
        seen_pages_by_source={1: {4}},
    )


_MIXED = json.dumps({"title": "Passiv üben", "exercises": [
    {"kind": "transform", "before": "Der Server speichert die Messwerte.",
     "after": "Die Messwerte werden vom Server gespeichert.", "page": 4},
    {"kind": "cloze", "sentence": "Die Messwerte werden vom Server gespeichert.",
     "form_span": "werden", "base_form": "werden", "page": 4},
    {"kind": "statement", "statement": "Die Messwerte werden vom Server gespeichert.",
     "answer": True, "page": 4},
    {"kind": "choice", "before": "Das Team prüfte die Akte.",
     "after": "Die Akte wurde vom Team geprüft.",
     "wrong": ["Die Akte wird vom Team geprüft.", "Die Akte ist vom Team geprüft."],
     "page": 4},
]})


@pytest.fixture
def attributed(monkeypatch):
    monkeypatch.setattr(
        "src.features.ai_assistant.tasks.language_training._source_grammar"
        ".attach_chips_cited", lambda items, claims, ctx, **kw: items)


def _generate(response=_MIXED, count=4):
    client, calls = _client(response)
    items, title, header = generate_grammar_from_source(
        client, "m", _ctx(), _TOPIC, count, locale="de")
    return items, title, header, calls


# ─── One set, four formats ───────────────────────────────────────────────────

def test_the_prompt_orders_the_formats_by_number(attributed):
    # A statement of intent has no effect, a number does. 10 plus 2 spare make 3 per format.
    _, _, _, calls = _generate(count=10)
    system = calls[0][0]["content"]
    for kind in KINDS:
        assert f'3 of kind "{kind}"' in system


def test_every_item_starts_with_a_bold_instruction(attributed):
    """Without an instruction the learner does not know what to do."""
    items, _, _, _ = _generate()
    for item in items:
        assert item["front"].startswith("**")
        assert "**\n\n" in item["front"]


def test_each_format_becomes_the_row_its_view_expects(attributed):
    items, _, _, _ = _generate()
    transform, cloze, statement, choice = items

    # Reshaping: free text, no options.
    assert transform["front"].endswith("Der Server speichert die Messwerte.")
    assert transform["back"] == "Die Messwerte werden vom Server gespeichert."
    assert "options" not in transform

    # Gap: the sentence with ___ comes first, free text, no options.
    assert "___" in cloze["front"]
    assert cloze["back"] == "werden"
    assert "options" not in cloze

    # True/false: two fixed labels, not named by the model.
    assert statement["options"] == ["Richtig", "Falsch"]
    assert statement["correct_idx"] == 0

    # Multiple choice: same before/after shape as transform, no gap, three options.
    assert "___" not in choice["front"]
    assert choice["front"].endswith("Das Team prüfte die Akte.")
    assert choice["back"] == "Die Akte wurde vom Team geprüft."
    assert choice["options"] == [
        "Die Akte wurde vom Team geprüft.",
        "Die Akte wird vom Team geprüft.",
        "Die Akte ist vom Team geprüft.",
    ]
    assert choice["correct_idx"] == 0


def test_a_false_statement_points_at_falsch(attributed):
    response = json.dumps({"title": "T", "exercises": [
        {"kind": "statement", "statement": "Die Messwerte werden vom Server gespeichert.",
         "answer": False},
    ]})
    items, _, _, _ = _generate(response, count=1)
    assert items[0]["correct_idx"] == 1
    assert items[0]["back"] == "Falsch"


def test_the_verdict_labels_follow_the_locale(attributed):
    client, _ = _client(json.dumps({"title": "T", "exercises": [
        {"kind": "statement", "statement": "The values are stored by the server.",
         "answer": True}]}))
    items, _, _ = generate_grammar_from_source(
        client, "m", _ctx(), _TOPIC, 1, locale="en")
    assert items[0]["options"] == ["True", "False"]


def test_only_the_transform_carries_the_worked_pattern(attributed):
    """Only the reshaping needs a pattern, otherwise it would be ballast."""
    items, _, _, _ = _generate()
    assert items[0]["extras"]["pattern_front"] == _TOPIC["example"]["before"]
    assert items[0]["extras"]["pattern_back"] == _TOPIC["example"]["after"]
    for item in items[1:]:
        assert not item.get("extras")


def test_the_set_carries_no_header_anymore(attributed):
    # A mixed set no longer has a shared pattern.
    _, _, header, _ = _generate()
    assert header == {}


_GOOD_FOUR = [
    {"kind": "transform", "before": "Der Server speichert die Messwerte.",
     "after": "Die Messwerte werden vom Server gespeichert."},
    {"kind": "cloze", "sentence": "Die Messwerte werden vom Server gespeichert.",
     "form_span": "werden", "base_form": "werden"},
    {"kind": "statement", "statement": "Die Eingaben werden von der Software geprüft.",
     "answer": True},
    {"kind": "choice", "before": "Die Software prüft die Eingaben.",
     "after": "Die Eingaben werden von der Software geprüft.",
     "wrong": ["Die Eingaben wurden von der Software geprüft.",
               "Die Eingaben sind von der Software geprüft."]},
]

_BAD_FOUR = [
    {"kind": "transform", "before": "Was heißt das?", "after": "Egal."},
    {"kind": "cloze", "sentence": "Ohne Ausschnitt geht es nicht.", "form_span": "fehlt"},
    {"kind": "statement", "statement": "Zu kurz", "answer": True},
    {"kind": "choice", "before": "Was heißt das?", "after": "Egal."},
]


def test_an_unusable_item_of_any_kind_is_dropped(attributed):
    """Every format has its own filter."""
    response = json.dumps({"title": "T", "exercises": _BAD_FOUR + _GOOD_FOUR})
    items, _, _, _ = _generate(response, count=8)
    assert len(items) == 4
    assert items[0]["front"].endswith("Der Server speichert die Messwerte.")


def test_a_run_where_most_items_fail_is_discarded_entirely(attributed):
    """The minimum rate applies across all four formats."""
    response = json.dumps({"title": "T", "exercises": _BAD_FOUR + _GOOD_FOUR[:1]})
    items, title, header, _ = _generate(response, count=5)
    assert items == []
    assert title == ""
    assert header == {}


def test_the_prompt_names_the_base_form_field_for_cloze(attributed):
    """The requirement has to name the field the hint is built from."""
    _, _, _, calls = _generate()
    system = calls[0][0]["content"]
    assert "base_form" in system


def test_the_prompt_names_the_wrong_field_for_choice(attributed):
    """The requirement has to name the field the distractors are built from."""
    _, _, _, calls = _generate()
    system = calls[0][0]["content"]
    assert "'wrong'" in system


def test_the_prompt_ties_a_false_statement_to_the_target_form(attributed):
    """A false statement's error must sit in the target form, not some other rule."""
    _, _, _, calls = _generate()
    system = calls[0][0]["content"]
    assert "TARGET FORM ITSELF" in system


def test_the_prompt_ties_before_to_the_shape_examples_tense(attributed):
    """A new 'before' pulled from the source must not drift into a different tense than the shape."""
    _, _, _, calls = _generate()
    system = calls[0][0]["content"]
    assert "SAME tense as 'before' in the shape example" in system


def test_the_prompt_warns_against_an_invented_category_for_a_true_statement(attributed):
    """A 'true' statement must be idiomatic, and its explanation must not invent a category."""
    _, _, _, calls = _generate()
    system = calls[0][0]["content"]
    assert "Präpositionalobjekt" in system
    assert "Finalsatz" in system


def test_the_prompt_warns_against_a_gender_mismatched_preposition(attributed):
    """A contracted preposition must match the noun's gender in every kind, not only statement."""
    _, _, _, calls = _generate()
    system = calls[0][0]["content"]
    assert "zur besseren Verständnis" in system
    assert "zum besseren Verständnis" in system


def test_the_same_sentence_never_appears_twice(attributed):
    """The same exercise twice is wasted practice time."""
    pair = {"kind": "transform", "before": "Der Server speichert die Messwerte.",
            "after": "Die Messwerte werden vom Server gespeichert."}
    response = json.dumps({"title": "T", "exercises": [
        pair, dict(pair), dict(pair),
        {"kind": "transform", "before": "Die Software prüft die Eingaben.",
         "after": "Die Eingaben werden von der Software geprüft."},
    ]})
    items, _, _, _ = _generate(response, count=4)
    assert len(items) == 2


def test_a_short_draw_is_not_topped_up(attributed):
    """Four usable of eight ordered: the set stays at four, only the verdict call follows."""
    thin = json.dumps({"title": "T", "exercises": _GOOD_FOUR + _BAD_FOUR})
    full = json.dumps({"title": "T", "exercises": [
        {"kind": "transform", "before": f"Das Team prüft die Quelle {i} genau.",
         "after": f"Die Quelle {i} wird vom Team genau geprüft."} for i in range(4)
    ]})
    client, calls = _client_queue(thin, full)
    items, _, _ = generate_grammar_from_source(
        client, "m", _ctx(), _TOPIC, 8, locale="de")
    assert len(items) == 4
    assert len(calls) == 2


def test_a_surplus_of_one_format_fills_the_set_without_a_second_draw(attributed):
    """The one draw is the last draw, so the count beats the mix and the rest is never ordered."""
    many = json.dumps({"title": "T", "exercises": [
        {"kind": "transform", "before": f"Das Team prüft die Quelle {i} genau.",
         "after": f"Die Quelle {i} wird vom Team genau geprüft."} for i in range(8)
    ]})
    rest = json.dumps({"title": "T", "exercises": [
        {"kind": "cloze", "sentence": f"Die Quelle {i} wird vom Team geprüft.",
         "form_span": "wird", "base_form": "werden"} for i in range(2)
    ] + [
        {"kind": "statement", "statement": f"Die Quelle {i} wird vom Team geprüft.",
         "answer": True} for i in range(2)
    ] + [
        {"kind": "choice", "before": f"Das Team prüft die Akte {i}.",
         "after": f"Die Akte {i} wird vom Team geprüft.",
         "wrong": [f"Die Akte {i} wurde vom Team geprüft.",
                   f"Die Akte {i} ist vom Team geprüft."]} for i in range(2)
    ]})
    client, calls = _client_queue(many, rest)
    items, _, _ = generate_grammar_from_source(
        client, "m", _ctx(), _TOPIC, 8, locale="de")
    umformungen = [i for i in items if i.get("_kind") == "transform"]
    assert len(umformungen) == 8
    assert len(calls) == 2


def test_the_last_draw_fills_up_with_whatever_it_gets(attributed):
    """In the end the count matters more than the mix."""
    many = json.dumps({"title": "T", "exercises": [
        {"kind": "transform", "before": f"Das Team prüft die Quelle {i} genau.",
         "after": f"Die Quelle {i} wird vom Team genau geprüft."} for i in range(8)
    ]})
    client, _ = _client_queue(many)
    items, _, _ = generate_grammar_from_source(
        client, "m", _ctx(), _TOPIC, 8, locale="de")
    assert len(items) == 8


_BAD_CHOICE = {
    "kind": "choice", "before": "Was heißt das?",
    # A question cannot be transformed, same filter as transform.
    "after": "Egal.",
}


def test_a_failing_format_leaves_the_set_short(attributed):
    """One of four formats is unusable: three are saved, no replacement draw is ordered."""
    dauerhaft_schlecht = json.dumps({"title": "T", "exercises": _GOOD_FOUR[:3] + [_BAD_CHOICE]})
    ersatz = json.dumps({"title": "T", "exercises": [
        {"kind": "transform", "before": "Das Labor erhebt die Daten.",
         "after": "Die Daten werden vom Labor erhoben."},
    ]})
    client, calls = _client_queue(dauerhaft_schlecht, ersatz)
    items, _, _ = generate_grammar_from_source(
        client, "m", _ctx(), _TOPIC, 4, locale="de")

    assert len(items) == 3
    # One generation call plus the one verdict call at the end.
    assert len(calls) == 2


def test_a_full_draw_costs_no_second_generation_call(attributed):
    """One generation call plus the one verdict call at the end, no top-up round."""
    client, calls = _client_queue(json.dumps({"title": "T", "exercises": _GOOD_FOUR}))
    generate_grammar_from_source(client, "m", _ctx(), _TOPIC, 4, locale="de")
    assert len(calls) == 2


def test_an_item_the_verifier_rejects_is_dropped(attributed):
    """The model-based check catches what no code filter can: a sentence that only
    reads wrong once the answer sits in it."""
    gen = json.dumps({"title": "T", "exercises": [
        {"kind": "transform", "before": "Der Server speichert die Messwerte.",
         "after": "Die Messwerte werden vom Server gespeichert."},
        {"kind": "transform", "before": "Das Team prüft die Akte.",
         "after": "Die Akte wird vom Team geprüft."},
    ]})
    verdict = json.dumps({"verdicts": [{"i": 0, "ok": False, "why": "kaputt"}]})
    client, _ = _client_queue(gen, verdict)
    # Both exercises share one kind, so the plan is met in a single generation
    # call and the second call is unambiguously the verdict check.
    items, _, _ = generate_grammar_from_source(
        client, "m", _ctx(), _TOPIC, 2, locale="de", kinds=["transform"])
    assert len(items) == 1
    assert items[0]["front"].endswith("Das Team prüft die Akte.")


def test_an_exercise_that_repeats_the_worked_example_is_dropped(attributed):
    """The pattern sentence must not appear as an exercise itself."""
    ex = _TOPIC["example"]
    response = json.dumps({"title": "T", "exercises": [
        {"kind": "transform", "before": ex["before"], "after": ex["after"]},
        {"kind": "transform", "before": "Das Team schreibt den Bericht.",
         "after": "Der Bericht wird vom Team geschrieben."},
    ]})
    items, _, _, _ = _generate(response, count=2)
    assert len(items) == 1
    assert items[0]["front"].endswith("Das Team schreibt den Bericht.")


def test_the_example_is_also_blocked_for_the_other_formats(attributed):
    # As a gapped or multiple choice sentence it would still be the pattern sentence.
    ex = _TOPIC["example"]
    response = json.dumps({"title": "T", "exercises": [
        {"kind": "cloze", "sentence": ex["before"], "form_span": "erklärt",
         "base_form": "erklären"},
        {"kind": "transform", "before": "Das Team schreibt den Bericht.",
         "after": "Der Bericht wird vom Team geschrieben."},
    ]})
    items, _, _, _ = _generate(response, count=2)
    assert len(items) == 1


def test_a_sentence_that_names_the_target_form_is_dropped(attributed):
    """A sentence naming the target form is a statement about the grammar."""
    response = json.dumps({"title": "T", "exercises": [
        {"kind": "transform", "before": "Das Team schreibt den Bericht.",
         "after": "Der Bericht wird vom Team geschrieben."},
        {"kind": "cloze", "sentence": "Im Passiv steht das Objekt vorn.",
         "form_span": "steht", "base_form": "stehen"},
    ]})
    items, _, _, _ = _generate(response, count=2)
    assert len(items) == 1
    assert items[0]["front"].endswith("Das Team schreibt den Bericht.")


def test_the_prompt_forbids_reusing_the_worked_example(attributed):
    _, _, _, calls = _generate()
    system = calls[0][0]["content"]
    assert "never reuse" in system.lower()


# ─── More than one musterweg ─────────────────────────────────────────────────

_MULTI_TOPIC = {
    "id": 2,
    "label": "Modalsätze",
    "rule": "Input: an action and its means. Output: one sentence joining them, "
            "an indem-clause or a dadurch-dass-clause are equally correct.",
    "example": {"before": "Er beruhigt sich. Er hört Musik.",
                "after": "Er beruhigt sich, indem er Musik hört."},
    "examples": [
        {"before": "Er beruhigt sich. Er hört Musik.",
         "after": "Er beruhigt sich, indem er Musik hört."},
        {"before": "Sie schont die Umwelt. Sie fährt Rad.",
         "after": "Sie schont die Umwelt, indem sie Rad fährt."},
    ],
}


def test_the_prompt_lists_every_musterweg_when_a_topic_has_more_than_one(attributed):
    client, calls = _client(_MIXED)
    generate_grammar_from_source(client, "m", _ctx(), _MULTI_TOPIC, 4, locale="de")
    system = calls[0][0]["content"]
    for pair in _MULTI_TOPIC["examples"]:
        assert pair["before"] in system
        assert pair["after"] in system


def test_the_second_musterweg_sentence_is_also_blocked_as_an_exercise(attributed):
    """Every stored pattern sentence is off limits, not only the first."""
    second = _MULTI_TOPIC["examples"][1]
    response = json.dumps({"title": "T", "exercises": [
        {"kind": "transform", "before": second["before"], "after": second["after"]},
        {"kind": "transform", "before": "Das Team schreibt den Bericht.",
         "after": "Der Bericht wird vom Team geschrieben."},
    ]})
    client, _ = _client(response)
    items, _, _ = generate_grammar_from_source(
        client, "m", _ctx(), _MULTI_TOPIC, 2, locale="de")
    assert len(items) == 1
    assert items[0]["front"].endswith("Das Team schreibt den Bericht.")


def test_an_unknown_kind_is_dropped_rather_than_guessed(attributed):
    response = json.dumps({"title": "T", "exercises": [
        {"kind": "wortschatz", "before": "a b c.", "after": "c b a."},
        {"kind": "transform", "before": "Der Server speichert die Messwerte.",
         "after": "Die Messwerte werden vom Server gespeichert."},
    ]})
    items, _, _, _ = _generate(response, count=2)
    assert len(items) == 1


# ─── The plan ────────────────────────────────────────────────────────────────

def test_the_plan_fills_exactly_the_requested_count():
    for count in (1, 4, 5, 10, 15, 20):
        assert len(item_plan(count)) == count


def test_twelve_items_split_evenly_across_the_four_formats():
    plan = item_plan(12)
    for kind in KINDS:
        assert plan.count(kind) == 3


def test_a_count_that_does_not_divide_gives_the_front_formats_one_more():
    """Round robin means the front formats get one more."""
    plan = item_plan(5)
    assert plan.count(KINDS[0]) == 2
    assert all(plan.count(k) == 1 for k in KINDS[1:])


def test_every_format_appears_as_soon_as_there_is_room():
    assert set(item_plan(4)) == set(KINDS)


def test_a_single_item_takes_the_first_format():
    assert item_plan(1) == [KINDS[0]]


def test_an_empty_or_negative_count_yields_no_plan():
    assert item_plan(0) == []
    assert item_plan(-3) == []


# ─── Richtig/Falsch ──────────────────────────────────────────────────────────

def test_a_statement_needs_text_and_a_verdict():
    assert is_usable_statement("Die Arbeit wird korrigiert.", True)
    assert is_usable_statement("Die Arbeit wird korrigiert.", False)


@pytest.mark.parametrize("text, verdict", [
    ("", True),
    ("   ", False),
    ("Die Arbeit wird korrigiert.", None),
    ("Die Arbeit wird korrigiert.", "ja"),
    ("Zu kurz", True),
])
def test_a_statement_without_both_halves_is_dropped(text, verdict):
    assert not is_usable_statement(text, verdict)


def test_a_statement_that_asks_something_is_dropped():
    # True/false judges a statement, a question has no truth value.
    assert not is_usable_statement("Ist das korrektes Passiv?", True)


# ─── Cloze ───────────────────────────────────────────────────────────────────

def test_a_gap_sentence_with_a_span_is_usable():
    assert is_usable_cloze("Das Buch der Dozentin ist interessant.", "der")


def test_a_sentence_without_a_span_is_dropped():
    assert not is_usable_cloze("Das Buch der Dozentin ist interessant.", "  ")


def test_a_span_that_swallows_the_whole_sentence_is_dropped():
    # Only a gap and nothing else is no exercise but an empty field.
    assert not is_usable_cloze("Irgendwas", "Irgendwas")


def test_the_gap_may_stand_at_the_end_of_the_sentence():
    # The excerpt may be the last word, the period stays behind it.
    assert is_usable_cloze("Die Arbeit wird von der Dozentin korrigiert.", "korrigiert")


# ─── The instruction on the exercise ─────────────────────────────────────────

def test_every_item_carries_its_own_task_line():
    """A bare sentence without an instruction was the reported case."""
    from src.features.ai_assistant.tasks.language_training._source_grammar import task_line
    for kind in KINDS:
        assert task_line(kind, "de", "Passiv Präsens").strip()
        assert task_line(kind, "en", "Passive present").strip()


@pytest.mark.parametrize("kind", KINDS)
def test_every_task_line_names_the_target_form(kind):
    """Without the target form in the text the learner does not know what to watch for."""
    from src.features.ai_assistant.tasks.language_training._source_grammar import task_line
    assert "Passiv Präsens" in task_line(kind, "de", "Passiv Präsens")
    assert "Passive present" in task_line(kind, "en", "Passive present")


def test_a_gap_shows_the_base_form_next_to_it(attributed):
    """The base-form hint sits right after the gap, a hint a click could otherwise skip."""
    response = json.dumps({"title": "T", "exercises": [
        {"kind": "cloze", "sentence": "Der Bericht wird vom Team geschrieben.",
         "form_span": "wird", "base_form": "werden"},
    ]})
    items, _, _, _ = _generate(response, count=1)
    assert "___ (werden)" in items[0]["front"]


def test_a_base_form_that_would_leak_the_answer_is_dropped(attributed):
    """A base form identical to the answer is not a hint, it is the solution."""
    response = json.dumps({"title": "T", "exercises": [
        {"kind": "cloze", "sentence": "Der Bericht wird vom Team geschrieben.",
         "form_span": "wird", "base_form": "wird"},
    ]})
    items, _, _, _ = _generate(response, count=1)
    assert "(wird)" not in items[0]["front"]


def test_a_choice_with_two_distinct_wrong_options_gets_three_options(attributed):
    response = json.dumps({"title": "T", "exercises": [
        {"kind": "choice", "before": "Das Team schreibt den Bericht.",
         "after": "Der Bericht wird vom Team geschrieben.",
         "wrong": ["Der Bericht wurde vom Team geschrieben.",
                   "Der Bericht ist vom Team geschrieben."]},
    ]})
    items, _, _, _ = _generate(response, count=1)
    assert items[0]["options"] == [
        "Der Bericht wird vom Team geschrieben.",
        "Der Bericht wurde vom Team geschrieben.",
        "Der Bericht ist vom Team geschrieben.",
    ]
    assert items[0]["correct_idx"] == 0


@pytest.mark.parametrize("wrong", [
    [],
    ["Der Bericht wird vom Team geschrieben."],  # repeats the correct answer
    ["Egal.", "Egal."],  # the same wrong sentence twice is only one real option
    ["Was schreibt das Team?", "Egal."],  # a question cannot be an option either
])
def test_a_choice_with_too_few_distinct_wrong_options_is_dropped(attributed, wrong):
    """Fewer than two distinct, usable wrong options means no real choice to make."""
    response = json.dumps({"title": "T", "exercises": [
        {"kind": "choice", "before": "Das Team schreibt den Bericht.",
         "after": "Der Bericht wird vom Team geschrieben.", "wrong": wrong},
    ]})
    items, _, _, _ = _generate(response, count=1)
    assert items == []


def test_an_unknown_language_falls_back_to_english(monkeypatch):
    from src.features.ai_assistant.tasks.language_training import _source_grammar
    # The phrasing is picked at random, pin it so the comparison is not flaky.
    monkeypatch.setattr(_source_grammar.random, "choice", lambda seq: seq[0])
    assert _source_grammar.task_line("transform", "fr", "X") == \
        _source_grammar.task_line("transform", "en", "X")


# ─── The inherited filter keeps running ──────────────────────────────────────

def test_the_free_text_filter_still_rejects_a_question():
    assert not is_usable_pair("Was bedeutet das?", "Etwas.")


def test_the_checker_sees_the_gap_as_the_learner_does(attributed):
    """Reported: the gap swallowed the noun, the full sentence alone hides that."""
    response = json.dumps({"title": "T", "exercises": [
        {"kind": "cloze",
         "sentence": "Das Geschäft bleibt wegen eines kurzen Umbaus geschlossen.",
         "form_span": "kurzen Umbaus", "base_form": "kurz"},
    ]})
    _, _, _, calls = _generate(response, count=1)
    pruefung = calls[-1][-1]["content"]
    assert 'gap shown: "Das Geschäft bleibt wegen eines ___ (kurz) geschlossen."' in pruefung
    assert 'answer typed: "kurzen Umbaus"' in pruefung


def test_the_prompt_keeps_the_noun_out_of_the_gap(attributed):
    _, _, _, calls = _generate(count=4)
    system = calls[0][0]["content"]
    assert 'form_span "neuen", base_form "neu"' in system


def test_the_prompt_keeps_the_noun_complement_when_shortening(attributed):
    _, _, _, calls = _generate(count=4)
    system = calls[0][0]["content"]
    assert '"Seit dem Bau der Brücke wächst der Handel."' in system
