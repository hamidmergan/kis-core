"""Grammatik-Quiz: Ankreuz-Aufgaben aus dem Quelltext.

Kein DB- und kein Netzzugriff. Der Generator bekommt einen Fake-Client, die
Attribution wird ausgehängt (sie hat eigene Tests in test_aia_tool_attribution).

Der Fall, der das Werkzeug überhaupt nötig macht: auf einem Grammatik-Arbeitsblatt
erzeugt das inhaltliche Quiz Fragen zum Inhalt ("Welche Gerichte wurden gekocht?")
statt zur Form. Hier muss genau das aussortiert werden.
"""

import json
import types

import pytest

from src.features.ai_assistant.tasks.language_training._context import QuelleContext
from src.services.aia_grammar_types import (
    GRAMMAR_TYPES, example_pair, get_grammar_type, worked_exercises,
)
from src.features.ai_assistant.tasks.language_training._source_grammar_choice import (
    generate_grammar_choice_from_source,
    is_usable_choice,
)


QUIZ_TYPE_ID = "grammar_quiz"
MARKER = "\n\nADAPT-MARKER: pitch this at level A1."

_TASK = "Bilden Sie das Passiv Präsens."
_SENTENCE = "Der Server speichert die Messwerte."
_CORRECT = "Die Messwerte werden vom Server gespeichert."
_WRONG = [
    "Die Messwerte sind vom Server gespeichert.",
    "Die Messwerte werden vom Server speichern.",
    "Die Messwerte wurden vom Server gespeichert.",
]


def _make_client(*contents):
    """Minimal OpenAI-client stand-in: records every call, answers in order.

    One content repeats forever, several are handed out one per call, which is what
    the retry needs.
    """
    calls = []
    queue = list(contents)

    def create(model, messages, **kwargs):
        calls.append(messages)
        content = queue.pop(0) if len(queue) > 1 else queue[0]
        message = types.SimpleNamespace(content=content)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])

    return types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
    ), calls


def _satz(front):
    """Der Aufgabensatz aus einem front-Feld, ohne die fette Anweisung davor."""
    return front.split("\n\n", 1)[1]


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


def _exercise(task=_TASK, sentence=_SENTENCE, options=None, correct_idx=0, explanation=""):
    return {
        "task": task,
        "sentence": sentence,
        "options": [_CORRECT] + _WRONG if options is None else options,
        "correct_idx": correct_idx,
        "explanation": explanation,
    }


def _response(*exercises, title="Passiv im Datenmanagement"):
    return json.dumps({"title": title, "exercises": list(exercises)})


@pytest.fixture
def attributed(monkeypatch):
    """Record what attribution was asked for, without touching pgvector."""
    seen: dict = {}

    def fake_attach(items, claims, ctx, **kwargs):
        seen["claims"] = list(claims)
        seen["items"] = [dict(i) for i in items]
        return items

    monkeypatch.setattr(
        "src.features.ai_assistant.tasks.language_training._source_grammar_choice"
        ".attach_chips_cited",
        fake_attach,
    )
    return seen


def _generate(response=None, count=1, adaptive_suffix="", *more_responses):
    client, calls = _make_client(response or _response(_exercise()), *more_responses)
    items, title, header = generate_grammar_choice_from_source(
        client, "m", _ctx(), get_grammar_type(QUIZ_TYPE_ID), count, locale="de",
        adaptive_suffix=adaptive_suffix,
    )
    return items, title, header, calls


# ─── Katalog ──────────────────────────────────────────────────────────────────

def test_the_quiz_type_is_the_first_entry_so_the_dialog_preselects_it():
    # The create dialog picks types[0]. Anything else costs the learner a click and
    # breaks "works exactly like the quiz".
    assert GRAMMAR_TYPES[0]["id"] == QUIZ_TYPE_ID


def test_the_quiz_type_answers_by_ticking():
    assert get_grammar_type(QUIZ_TYPE_ID)["format"] == "choice"


def test_the_quiz_type_ships_wrong_forms_for_the_prompt_shape():
    # The worked pair alone is not enough here: without three wrong forms the model
    # has no example of what a distractor looks like and invents content options.
    entry = get_grammar_type(QUIZ_TYPE_ID)
    for locale in ("de", "en"):
        wrong = entry["wrong"][locale]
        assert len(wrong) == 3
        assert example_pair(entry, locale)["after"] not in wrong


def test_no_worked_example_asks_for_a_subordinate_clause():
    """Joining two sentences with a conjunction is not a clean form exercise: the
    conjunction has to fit the meaning, and the model picks one that does not ("Die
    Forschung ist schwierig, obwohl sie wichtig ist"). The examples steer what the
    model produces, so they must not show one."""
    entry = get_grammar_type(QUIZ_TYPE_ID)
    for locale in ("de", "en"):
        shown = " ".join(
            ex["task"] + " " + ex["sentence"] + " " + " ".join(ex["options"])
            for ex in worked_exercises(entry, locale)
        ).lower()
        for conjunction in ("weil", "obwohl", "dass", "because", "although"):
            assert conjunction not in shown.split()
    assert "subordinate" not in entry["rule"].lower()


def test_the_free_text_types_keep_their_format():
    for entry in GRAMMAR_TYPES:
        if entry["id"] != QUIZ_TYPE_ID:
            assert entry["format"] == "text"


# ─── Aufbau der Aufgaben ─────────────────────────────────────────────────────

def test_an_item_carries_task_and_sentence_in_front(attributed):
    items, _, _, _ = _generate()
    assert items[0]["front"] == f"**{_TASK}**\n\n{_SENTENCE}"


def test_an_item_carries_the_options_and_the_correct_answer(attributed):
    items, _, _, _ = _generate()
    assert items[0]["options"] == [_CORRECT] + _WRONG
    assert items[0]["correct_idx"] == 0
    assert items[0]["back"] == _CORRECT


def test_the_correct_answer_follows_the_index(attributed):
    shuffled = [_WRONG[0], _WRONG[1], _CORRECT, _WRONG[2]]
    items, _, _, _ = _generate(_response(_exercise(options=shuffled, correct_idx=2)))
    assert items[0]["back"] == _CORRECT


def test_an_empty_explanation_becomes_none_rather_than_an_empty_string(attributed):
    items, _, _, _ = _generate()
    assert items[0]["explanation"] is None


def test_the_explanation_is_kept_when_the_model_writes_one(attributed):
    items, _, _, _ = _generate(_response(_exercise(explanation="werden plus Partizip II.")))
    assert items[0]["explanation"] == "werden plus Partizip II."


def test_a_ticking_set_has_no_worked_pair_above_the_exercises(attributed):
    # Every item states its own task, so a set-level pattern would be wrong as soon
    # as the set mixes forms, which is the normal case here.
    _, _, header, _ = _generate()
    assert header == {}


def test_generation_respects_the_requested_count(attributed):
    response = _response(_exercise(), _exercise(sentence="Die Software prüft die Eingaben."))
    items, _, _, _ = _generate(response, count=1)
    assert len(items) == 1


def test_the_title_falls_back_to_the_type_label(attributed):
    items, title, _, _ = _generate(_response(_exercise(), title=""))
    assert items
    assert title == get_grammar_type(QUIZ_TYPE_ID)["label"]["de"]


def test_attribution_gets_the_correct_option_as_the_claim(attributed):
    # The solved sentence carries the source content. One sentence has one origin.
    _generate()
    assert attributed["claims"] == [_CORRECT]


def test_generation_prompt_asks_the_model_where_it_took_the_material_from(attributed):
    # Same reason as the free-text drill: invented sentences are not found again by a
    # post-hoc search, so the model names the page while it still knows it.
    _, _, _, calls = _generate()
    system = _system_of(calls)
    assert '"page"' in system
    assert "S. " in system


def test_items_carry_the_page_the_model_cited(attributed):
    _generate(_response(_exercise() | {"page": 4}))
    assert [i.get("_page") for i in attributed["items"]] == [4]


# ─── Aussortieren ────────────────────────────────────────────────────────────

def test_options_that_differ_in_content_instead_of_form_are_dropped(attributed):
    """The reported bug in one test: four different dishes are a content question,
    not a grammar exercise, however plausible the sentence around them looks."""
    content = [
        "Pizza und Pasta", "Tacos und Fajitas",
        "Morghe Zaferani oder Kabuli Palau", "Sushi und Tempura",
    ]
    assert not is_usable_choice(
        "Welche Gerichte wurden gekocht?",
        "Laut Text wurden am Samstagabend welche Gerichte gekocht?",
        content, 0,
    )


def test_four_variants_of_one_sentence_are_accepted():
    assert is_usable_choice(_TASK, _SENTENCE, [_CORRECT] + _WRONG, 0)


def test_the_form_filter_needs_no_word_list_and_works_in_other_languages():
    correct = "The values are stored by the server."
    wrong = [
        "The values is stored by the server.",
        "The values are store by the server.",
        "The values were stored by the server.",
    ]
    assert is_usable_choice("Form the passive.", "The server stores the values.",
                            [correct] + wrong, 0)
    assert not is_usable_choice("Form the passive.", "The server stores the values.",
                                [correct, "Pizza and pasta", "Sushi", "Tacos"], 0)


@pytest.mark.parametrize("options, correct_idx", [
    ([_CORRECT] + _WRONG[:2], 0),                       # only three options
    ([_CORRECT] + _WRONG + ["noch eine"], 0),           # five options
    ([_CORRECT, _CORRECT] + _WRONG[:2], 0),             # a duplicate option
    ([_CORRECT, "die messwerte werden vom server gespeichert!"] + _WRONG[:2], 0),  # dup bar noise
    ([_CORRECT] + _WRONG, 4),                           # index out of range
    ([_CORRECT] + _WRONG, None),                        # no index at all
])
def test_a_malformed_option_list_is_dropped(options, correct_idx):
    assert not is_usable_choice(_TASK, _SENTENCE, options, correct_idx)


@pytest.mark.parametrize("task, sentence", [
    ("", _SENTENCE),
    (_TASK, ""),
    (_TASK, "Passiv"),  # a heading, not a sentence to transform
])
def test_an_item_without_a_task_or_a_real_sentence_is_dropped(task, sentence):
    assert not is_usable_choice(task, sentence, [_CORRECT] + _WRONG, 0)


@pytest.mark.parametrize("options", [
    [_SENTENCE] + _WRONG,                    # the sentence IS the marked solution
    [_CORRECT, _SENTENCE] + _WRONG[:2],      # the sentence is one of the distractors
    [_CORRECT, "der server  speichert die messwerte!"] + _WRONG[:2],  # bar case and noise
])
def test_an_option_that_repeats_the_given_sentence_is_dropped(options):
    """Seen in a real run: "Die Tür ist geöffnet." with "Die Tür ist geöffnet." as the
    right answer. Nothing was transformed, so the exercise teaches nothing — and as a
    distractor the same sentence is simply confusing. Same rule the free-text drill
    already applies to an unchanged solution."""
    assert not is_usable_choice(_TASK, _SENTENCE, options, 0)


def test_an_exercise_that_copies_the_worked_example_is_dropped(attributed):
    """Also seen in a real run: the model shipped the prompt's own example sentence as
    exercise one. The example is a shape to copy, not material."""
    entry = get_grammar_type(QUIZ_TYPE_ID)
    shipped = example_pair(entry, "de")
    copied = _exercise(
        sentence=shipped["before"],
        options=[shipped["after"], *entry["wrong"]["de"]],
    )
    good = [_exercise(sentence=s) for s in ("Die Software prüft die Eingaben.",
                                            "Das Labor erhebt die Daten.",
                                            "Der Server speichert die Messwerte.")]
    items, _, _, _ = _generate(_response(copied, *good), count=4)
    assert shipped["before"] not in [_satz(i["front"]) for i in items]
    assert len(items) == 3


def test_the_prompt_forbids_reusing_the_worked_example(attributed):
    _, _, _, calls = _generate()
    assert "never reuse" in _system_of(calls).lower()


def test_the_prompt_demands_more_than_one_form_across_the_set(attributed):
    """Measured: told only to "vary" the forms, the model drilled Passiv Präsens ten
    times on a handout that covers six tenses. The demand has to be countable."""
    _, _, _, calls = _generate()
    assert "at least three different" in _system_of(calls).lower()


def test_a_bad_item_is_dropped_while_the_run_survives(attributed):
    good = [_exercise(sentence="Die Software prüft die Eingaben."),
            _exercise(sentence="Das Labor erhebt die Daten."),
            _exercise(sentence="Der Server speichert die Messwerte.")]
    bad = _exercise(options=["Pizza", "Pasta", "Sushi", "Tacos"])
    items, _, _, _ = _generate(_response(*good, bad), count=4)
    assert len(items) == 3


def test_a_run_of_mostly_content_questions_is_discarded(attributed):
    """Half broken must fail the set rather than reach the learner."""
    bad = _exercise(options=["Pizza", "Pasta", "Sushi", "Tacos"])
    bad_run = _response(_exercise(), bad, bad, bad)
    items, title, header, _ = _generate(bad_run, 4, "", bad_run)
    assert items == []
    assert title == ""
    assert header == {}


# ─── Zweiter Versuch ─────────────────────────────────────────────────────────

_FOUR_TIMES_THE_SAME = _response(*[
    _exercise(sentence=s, options=[_CORRECT] * 4)
    for s in ("Der Server speichert die Messwerte.", "Die Software prüft die Eingaben.")
])


def test_both_draws_are_kept_together(attributed):
    """A half-wasted draw still holds good exercises. Throwing them away was what made
    a set fail on lecture sources, where the model reliably wastes some of every draw."""
    half = _response(_exercise(), _exercise(sentence="X Y", options=[_CORRECT] * 4))
    rest = _response(_exercise(sentence="Die Software prüft die Eingaben."),
                     _exercise(sentence="Das Labor erhebt die Daten."))
    items, _, _, calls = _generate(half, 4, "", rest)
    assert [_satz(i["front"]) for i in items] == [
        _SENTENCE, "Die Software prüft die Eingaben.", "Das Labor erhebt die Daten."]
    assert len(calls) == 2


def test_the_same_sentence_from_both_draws_is_kept_once(attributed):
    same = _response(*[_exercise(sentence=s) for s in (
        "Die Software prüft die Eingaben.", "Das Labor erhebt die Daten.",
        "Der Server speichert die Messwerte.")])
    items, _, _, calls = _generate(same, 5, "", same)
    assert len(calls) == 2
    assert len(items) == 3


def test_a_wasted_first_call_is_retried_once(attributed):
    """Measured against the live model: it keeps the four-option rule only sometimes.
    One run came back with the same sentence in all four slots, ten times over, and the
    learner was left with a failed set. A second draw is cheaper than that."""
    good = _response(_exercise(), _exercise(sentence="Die Software prüft die Eingaben."))
    items, _, _, calls = _generate(_FOUR_TIMES_THE_SAME, 2, "", good)
    assert len(items) == 2
    assert len(calls) == 2


def test_a_thin_result_still_ships_rather_than_failing(attributed):
    """Three good exercises beat a failed set. The per-item filters already decide
    quality, so a short set is short, not bad."""
    thin = _response(*([_exercise(sentence=s) for s in (
        "Die Software prüft die Eingaben.", "Das Labor erhebt die Daten.",
        "Der Server speichert die Messwerte.")]
        + [_exercise(sentence="X Y", options=[_CORRECT] * 4)] * 7))
    items, _, _, _ = _generate(thin, 10, "", thin)
    assert len(items) == 3


def test_fewer_than_three_usable_exercises_fails_the_set(attributed):
    thin = _response(*([_exercise()] + [_exercise(sentence="X Y", options=[_CORRECT] * 4)] * 9))
    items, title, _, _ = _generate(thin, 10, "", thin)
    assert items == []
    assert title == ""


def test_a_full_first_call_costs_no_second_one(attributed):
    """The provider limit is shared across the university, so a second draw only
    happens when the first one came up short."""
    good = _response(_exercise(), _exercise(sentence="Die Software prüft die Eingaben."))
    _, _, _, calls = _generate(good, 2)
    assert len(calls) == 1


def test_the_set_still_fails_when_the_retry_is_wasted_too(attributed):
    items, title, _, calls = _generate(_FOUR_TIMES_THE_SAME, 2, "", _FOUR_TIMES_THE_SAME)
    assert items == []
    assert title == ""
    assert len(calls) == 2


# ─── Prompt ──────────────────────────────────────────────────────────────────

def test_the_prompt_shows_a_finished_exercise_as_a_shape_to_copy(attributed):
    # Rules alone get ignored by the chat model. Only an example steers the format,
    # same lesson as the overview prose and the free-text grammar drill.
    _, _, _, calls = _generate()
    system = _system_of(calls)
    entry = get_grammar_type(QUIZ_TYPE_ID)
    pair = example_pair(entry, "de")
    assert "SHAPE TO COPY" in system
    assert pair["before"] in system
    assert pair["after"] in system
    for wrong in entry["wrong"]["de"]:
        assert wrong in system


def test_the_prompt_rules_out_content_questions_by_example(attributed):
    # The exact failure from the screenshot, spelled out as a counterexample.
    _, _, _, calls = _generate()
    system = _system_of(calls)
    assert "differ only in FORM" in system
    assert "content question" in system


def test_the_prompt_rules_out_repeated_options_by_example(attributed):
    """The second failure seen live: all four slots filled with the same sentence.
    A rule alone did not stop it, so it gets the same counterexample treatment."""
    _, _, _, calls = _generate()
    assert "the same sentence four times" in _system_of(calls)


def test_three_worked_exercises_are_shown_after_the_sources(attributed):
    """One example is not enough. Measured on a lecture context: one worked example gave
    0 and 2 of 10 usable exercises, three gave 4 and 7. The model copies form variants it
    sees, and a grammar handout supplies dozens of them itself, which is why the tool
    looked fine on one and failed on the other."""
    user = _generate()[3][0][1]["content"]
    entry = get_grammar_type(QUIZ_TYPE_ID)
    shown = [example_pair(entry, "de")["before"]] + [
        ex["sentence"] for ex in entry["more_examples"]["de"]
    ]
    assert len(shown) == 3
    for sentence in shown:
        assert sentence in user


def test_the_extra_examples_are_barred_from_the_exercises_too(attributed):
    # Same reason as the first example: a shape must never come back as material.
    entry = get_grammar_type(QUIZ_TYPE_ID)
    extra = entry["more_examples"]["de"][0]
    copied = _exercise(sentence=extra["sentence"], options=extra["options"])
    good = [_exercise(sentence=s) for s in ("Die Software prüft die Eingaben.",
                                            "Das Labor erhebt die Daten.",
                                            "Der Server speichert die Messwerte.")]
    items, _, _, _ = _generate(_response(copied, *good), count=4)
    assert extra["sentence"] not in [_satz(i["front"]) for i in items]
    assert len(items) == 3


def test_the_example_is_repeated_after_the_sources(attributed):
    """Measured, and it decides whether the tool works at all: with the example only in
    the system prompt, a long lecture context produced 0 of 10 usable exercises, all
    four options the same string. Repeating it after the sources gave 9 of 10 from the
    same context. A grammar handout carries form variants itself and hides the problem,
    any other source does not."""
    _, _, _, calls = _generate()
    user = calls[0][1]["content"]
    entry = get_grammar_type(QUIZ_TYPE_ID)
    assert example_pair(entry, "de")["after"] in user
    for wrong in entry["wrong"]["de"]:
        assert wrong in user
    # And it has to come after the material, that is the whole point.
    assert user.index("Sources:") < user.index(example_pair(entry, "de")["after"])


def test_the_prompt_carries_the_rule_and_the_adaptive_block(attributed):
    _, _, _, calls = _generate(adaptive_suffix=MARKER)
    system = _system_of(calls)
    assert get_grammar_type(QUIZ_TYPE_ID)["rule"] in system
    assert MARKER in system
    # The whole point of the tool: sentences are written fresh from the source.
    assert "NEW" in system


def test_the_prompt_leaves_difficulty_to_the_level_alone(attributed):
    """Difficulty has exactly one source, the learner's CEFR level. A second screw in
    this prompt would contradict the adaptive block at B2 and above."""
    _, _, _, calls = _generate()
    system = _system_of(calls)
    assert "14 words" not in system
    assert "simple" not in system.lower().split("shape to copy")[0]
