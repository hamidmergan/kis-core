"""A grammar set mixes four formats, as a number in the prompt instead of an intent."""

import json
import types

import pytest

from src.features.ai_assistant.tasks.language_training._context import QuelleContext
from src.features.ai_assistant.tasks.language_training._source_grammar import (
    KINDS,
    generate_grammar_from_source,
    is_usable_choice,
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
     "form_span": "werden", "options": ["werden", "wurden", "sind", "waren"],
     "correct_idx": 0, "page": 4},
    {"kind": "statement", "statement": "Die Messwerte werden vom Server gespeichert.",
     "answer": True, "page": 4},
    {"kind": "choice", "task": "Bilden Sie das Passiv.",
     "sentence": "Die Software prüft die Eingaben.",
     "options": ["Die Eingaben werden von der Software geprüft.",
                 "Die Eingaben sind von der Software geprüft.",
                 "Die Eingaben werden von der Software prüfen.",
                 "Die Eingaben wurden von der Software geprüft."],
     "correct_idx": 0, "page": 4},
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
    # A statement of intent has no effect, a number does.
    _, _, _, calls = _generate(count=12)
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

    # Gap: the sentence with ___ comes first, plus four options to click.
    assert "___" in cloze["front"]
    assert cloze["back"] == "werden"
    assert len(cloze["options"]) == 4
    assert cloze["correct_idx"] == 0

    # True/false: two fixed labels, not named by the model.
    assert statement["options"] == ["Richtig", "Falsch"]
    assert statement["correct_idx"] == 0

    # Ankreuzen: Aufgabenzeile in front, vier Optionen.
    assert choice["front"].startswith("**Welcher Satz ist korrekt? Zielform: Passiv Präsens.**")
    assert len(choice["options"]) == 4
    assert choice["back"] == choice["options"][choice["correct_idx"]]


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
     "form_span": "werden", "options": ["werden", "wurden", "sind", "waren"],
     "correct_idx": 0},
    {"kind": "statement", "statement": "Die Eingaben werden von der Software geprüft.",
     "answer": True},
    {"kind": "choice", "task": "Bilden Sie das Passiv.",
     "sentence": "Die Software prüft die Eingaben.",
     "options": ["Die Eingaben werden von der Software geprüft.",
                 "Die Eingaben sind von der Software geprüft.",
                 "Die Eingaben werden von der Software prüfen.",
                 "Die Eingaben wurden von der Software geprüft."],
     "correct_idx": 0},
]

_BAD_FOUR = [
    {"kind": "transform", "before": "Was heißt das?", "after": "Egal."},
    {"kind": "cloze", "sentence": "Ohne Ausschnitt geht es nicht.", "form_span": "fehlt"},
    {"kind": "statement", "statement": "Zu kurz", "answer": True},
    {"kind": "choice", "task": "T", "sentence": "Der Server speichert Werte.",
     "options": ["a", "a", "b", "c"], "correct_idx": 0},
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


def test_the_prompt_demands_full_sentences_as_options(attributed):
    """The requirement has to name the shape the filter expects."""
    _, _, _, calls = _generate()
    system = calls[0][0]["content"]
    assert "complete sentence" in system.lower()


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


def test_a_short_draw_is_topped_up_to_the_requested_count(attributed):
    """A second attempt fetches the missing exercises."""
    thin = json.dumps({"title": "T", "exercises": _GOOD_FOUR + _BAD_FOUR})
    full = json.dumps({"title": "T", "exercises": [
        {"kind": "transform", "before": f"Das Team prüft die Quelle {i} genau.",
         "after": f"Die Quelle {i} wird vom Team genau geprüft."} for i in range(4)
    ]})
    client, calls = _client_queue(thin, full)
    items, _, _ = generate_grammar_from_source(
        client, "m", _ctx(), _TOPIC, 8, locale="de")
    assert len(items) == 8
    assert len(calls) >= 2


def test_the_top_up_asks_only_for_the_formats_that_are_missing(attributed):
    """The top-up has to ask specifically, otherwise the mix tips over."""
    only_transforms = json.dumps({"title": "T", "exercises": [
        {"kind": "transform", "before": f"Das Team prüft die Quelle {i} genau.",
         "after": f"Die Quelle {i} wird vom Team genau geprüft."} for i in range(4)
    ]})
    client, calls = _client_queue(only_transforms)
    generate_grammar_from_source(client, "m", _ctx(), _TOPIC, 8, locale="de")

    zweiter = calls[1][0]["content"]
    # Reshapings are full, they must not be asked for again.
    assert 'of kind "transform"' not in zweiter
    for kind in ("cloze", "statement", "choice"):
        assert f'of kind "{kind}"' in zweiter


def test_a_surplus_of_one_format_is_capped_at_the_plan(attributed):
    """Without a per-format cap the mix tips over on the first attempt already."""
    many = json.dumps({"title": "T", "exercises": [
        {"kind": "transform", "before": f"Das Team prüft die Quelle {i} genau.",
         "after": f"Die Quelle {i} wird vom Team genau geprüft."} for i in range(8)
    ]})
    rest = json.dumps({"title": "T", "exercises": [
        {"kind": "cloze", "sentence": f"Die Quelle {i} wird vom Team geprüft.",
         "form_span": "wird", "options": ["wird", "werden", "wurde", "ist"],
         "correct_idx": 0} for i in range(2)
    ] + [
        {"kind": "statement", "statement": f"Die Quelle {i} wird vom Team geprüft.",
         "answer": True} for i in range(2)
    ] + [
        {"kind": "choice", "task": "Welche Form ist richtig?",
         "sentence": f"Die Akte {i} wird vom Team geprüft.",
         "options": [f"Die Akte {i} wird vom Team geprüft.",
                     f"Die Akte {i} wird vom Team prüfen.",
                     f"Die Akte {i} ist vom Team geprüft.",
                     f"Die Akte {i} wurde vom Team geprüft."],
         "correct_idx": 0} for i in range(2)
    ]})
    client, _ = _client_queue(many, rest)
    items, _, _ = generate_grammar_from_source(
        client, "m", _ctx(), _TOPIC, 8, locale="de")
    umformungen = [i for i in items if "Forme den Satz" in i["front"]]
    assert len(umformungen) == 2
    assert len(items) == 8


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
    "kind": "choice", "task": "Bilden Sie das Passiv.",
    "sentence": "Der Server speichert die Messwerte.",
    # The exercise sentence stands as a WRONG option, the filter discards that every time.
    "options": ["Die Messwerte werden vom Server gespeichert.",
                "Der Server speichert die Messwerte.",
                "Die Messwerte sind vom Server gespeichert.",
                "Die Messwerte wurden vom Server gespeichert."],
    "correct_idx": 0,
}


def test_the_last_draw_stops_asking_for_the_format_that_keeps_failing(attributed):
    """In the last attempt a kind is asked for that has already delivered."""
    dauerhaft_schlecht = json.dumps({"title": "T", "exercises": _GOOD_FOUR[:3] + [_BAD_CHOICE]})
    client, calls = _client_queue(dauerhaft_schlecht)
    generate_grammar_from_source(client, "m", _ctx(), _TOPIC, 4, locale="de")

    assert len(calls) == 3
    dritter = calls[2][0]["content"]
    assert 'of kind "choice"' not in dritter, "diese Art scheitert, sie noch einmal zu bestellen bringt nichts"
    assert 'of kind "transform"' in dritter, "die Umformung hat geliefert, sie fuellt auf"


def test_the_count_stands_even_when_one_format_never_works(attributed):
    dauerhaft_schlecht = json.dumps({"title": "T", "exercises": _GOOD_FOUR[:3] + [_BAD_CHOICE]})
    ersatz = json.dumps({"title": "T", "exercises": [
        {"kind": "transform", "before": "Das Labor erhebt die Daten.",
         "after": "Die Daten werden vom Labor erhoben."},
    ]})
    client, _ = _client_queue(dauerhaft_schlecht, dauerhaft_schlecht, ersatz)
    items, _, _ = generate_grammar_from_source(
        client, "m", _ctx(), _TOPIC, 4, locale="de")

    assert len(items) == 4


def test_a_full_draw_costs_no_second_call(attributed):
    client, calls = _client_queue(json.dumps({"title": "T", "exercises": _GOOD_FOUR}))
    generate_grammar_from_source(client, "m", _ctx(), _TOPIC, 4, locale="de")
    assert len(calls) == 1


def test_the_top_up_never_repeats_a_sentence(attributed):
    same = json.dumps({"title": "T", "exercises": _GOOD_FOUR})
    client, _ = _client_queue(same, same)
    items, _, _ = generate_grammar_from_source(
        client, "m", _ctx(), _TOPIC, 8, locale="de")
    fronts = [i["front"] for i in items]
    assert len(fronts) == len(set(fronts))


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
        # With four options, so the exercise really fails on the pattern sentence.
        {"kind": "cloze", "sentence": ex["before"], "form_span": "erklärt",
         "options": ["erklärt", "erklären", "erklärte", "erklärt hat"],
         "correct_idx": 0},
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
         "form_span": "steht", "options": ["steht", "stehen", "stand", "gestanden"],
         "correct_idx": 0},
    ]})
    items, _, _, _ = _generate(response, count=2)
    assert len(items) == 1
    assert items[0]["front"].endswith("Das Team schreibt den Bericht.")


def test_the_prompt_forbids_reusing_the_worked_example(attributed):
    _, _, _, calls = _generate()
    system = calls[0][0]["content"]
    assert "never reuse" in system.lower()


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

# The code sets exactly one gap, which dropped four old checks.
_GAP_OPTIONS = ["der", "des", "dem", "den"]


def test_a_gap_sentence_needs_a_span_and_four_options():
    """Four options make the gap solvable and stay a decision about form."""
    assert is_usable_cloze("Das Buch der Dozentin ist interessant.", "der",
                           _GAP_OPTIONS, 0)


def test_a_gap_without_options_is_dropped():
    assert not is_usable_cloze("Das Buch der Dozentin ist interessant.", "der", [], None)


def test_a_gap_needs_exactly_four_options():
    assert not is_usable_cloze("Das Buch der Dozentin ist da.", "der", ["der", "des"], 0)


def test_two_identical_options_drop_the_gap():
    # The same answer twice: the learner can be right and wrong at once.
    assert not is_usable_cloze("Das Buch der Dozentin ist da.", "der",
                               ["der", "der", "des", "dem"], 0)


def test_the_marked_option_must_be_the_span():
    assert not is_usable_cloze("Das Buch der Dozentin ist da.", "der", _GAP_OPTIONS, 1)


def test_gap_options_may_be_single_words():
    """The word overlap filter explicitly does not apply to the gap."""
    assert is_usable_cloze("Der Bericht wird geschrieben.", "wird",
                           ["wird", "werden", "wurde", "ist"], 0)


def test_a_sentence_without_a_span_is_dropped():
    assert not is_usable_cloze("Das Buch der Dozentin ist interessant.", "  ",
                               _GAP_OPTIONS, 0)


def test_a_span_that_swallows_the_whole_sentence_is_dropped():
    # Only a gap and nothing else is no exercise but an empty field.
    assert not is_usable_cloze("Irgendwas", "Irgendwas",
                               ["Irgendwas", "b", "c", "d"], 0)


def test_the_gap_may_stand_at_the_end_of_the_sentence():
    # The excerpt may be the last word, the period stays behind it.
    assert is_usable_cloze("Die Arbeit wird von der Dozentin korrigiert.", "korrigiert",
                           ["korrigiert", "korrigieren", "korrigierte", "korrigiert hat"],
                           0)


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


def test_a_choice_that_asks_which_is_correct_does_not_repeat_the_sentence(attributed):
    """In this construction the question carries everything, a sentence above would be ballast."""
    satz = "Die Ergebnisse werden von der Betreuerin überprüft."
    response = json.dumps({"title": "T", "exercises": [
        {"kind": "choice", "task": "Welche Form ist richtig?", "sentence": satz,
         "options": [satz,
                     "Die Ergebnisse sind von der Betreuerin überprüft.",
                     "Die Ergebnisse werden von der Betreuerin überprüfen.",
                     "Die Ergebnisse wurden von der Betreuerin überprüft."],
         "correct_idx": 0},
    ]})
    items, _, _, _ = _generate(response, count=1)
    assert satz not in items[0]["front"]


def test_a_choice_that_transforms_keeps_its_sentence(attributed):
    # Different construction: the sentence is the template and is needed.
    response = json.dumps({"title": "T", "exercises": [
        {"kind": "choice", "task": "Bilden Sie das Passiv.",
         "sentence": "Die Software prüft die Eingaben.",
         "options": ["Die Eingaben werden von der Software geprüft.",
                     "Die Eingaben sind von der Software geprüft.",
                     "Die Eingaben werden von der Software prüfen.",
                     "Die Eingaben wurden von der Software geprüft."],
         "correct_idx": 0},
    ]})
    items, _, _, _ = _generate(response, count=1)
    assert "Die Software prüft die Eingaben." in items[0]["front"]


def test_an_unknown_language_falls_back_to_english():
    from src.features.ai_assistant.tasks.language_training._source_grammar import task_line
    assert task_line("transform", "fr", "X") == task_line("transform", "en", "X")


# ─── The two inherited filters keep running ──────────────────────────────────

def test_the_free_text_filter_still_rejects_a_question():
    assert not is_usable_pair("Was bedeutet das?", "Etwas.")


def test_the_choice_filter_still_rejects_four_content_options():
    # Four different contents instead of four forms, that is what the filter is for.
    assert not is_usable_choice(
        "Welche Gerichte wurden gekocht?", "Am Samstag wurde gekocht.",
        ["Pizza und Pasta", "Tacos und Fajitas", "Sushi und Tempura", "Suppe und Salat"],
        0,
    )


def test_the_sentence_may_be_the_correct_option():
    """The sentence as the correct option is a valid construction."""
    satz = "Die Arbeit wird von der Dozentin korrigiert."
    assert is_usable_choice(
        "Welche Form ist richtig?", satz,
        [satz,
         "Die Arbeit wird von der Dozentin korrigieren.",
         "Die Arbeit ist von der Dozentin korrigiert.",
         "Die Arbeit wurde von der Dozentin korrigiert."],
        0,
    )


def test_the_sentence_as_a_wrong_option_stays_forbidden():
    """As a wrong option it stays a giveaway."""
    satz = "Der Server speichert die Messwerte."
    assert not is_usable_choice(
        "Bilden Sie das Passiv.", satz,
        ["Die Messwerte werden vom Server gespeichert.",
         satz,
         "Die Messwerte sind vom Server gespeichert.",
         "Die Messwerte wurden vom Server gespeichert."],
        0,
    )


def test_the_choice_filter_accepts_four_form_variants():
    assert is_usable_choice(
        "Bilden Sie das Passiv Präsens.", "Der Server speichert die Messwerte.",
        ["Die Messwerte werden vom Server gespeichert.",
         "Die Messwerte sind vom Server gespeichert.",
         "Die Messwerte werden vom Server speichern.",
         "Die Messwerte wurden vom Server gespeichert."],
        0,
    )
