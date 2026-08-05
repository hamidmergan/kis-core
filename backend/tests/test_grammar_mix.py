"""Ein Grammatik-Set mischt vier Formate zu gleichen Teilen.

Das Format war früher eine Wahl im Dialog und steckte im Katalogeintrag. Es ist
aber kein Thema, sondern eine Darreichungsform, und ein Lernender profitiert mehr
davon, dieselbe Form auf vier Arten zu üben als zehnmal auf eine.

Der Plan ist eine ZAHL im Prompt, keine Absichtserklärung. Erfahrung aus dem
Grammatik-Quiz und dem Hörverstehen: "stelle abwechslungsreiche Aufgaben" wirkt
nicht, "genau 4 Aufgaben der Art X" wirkt.

Kein DB- und kein Netzzugriff.
"""

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
    {"kind": "cloze", "sentence": "Die Messwerte ___ vom Server gespeichert.",
     "answer": "werden", "page": 4},
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


# ─── Ein Set, vier Formate ───────────────────────────────────────────────────

def test_the_prompt_orders_the_formats_by_number(attributed):
    # Eine Absichtserklaerung wirkt nicht, eine Zahl wirkt.
    _, _, _, calls = _generate(count=12)
    system = calls[0][0]["content"]
    for kind in KINDS:
        assert f'3 of kind "{kind}"' in system


def test_each_format_becomes_the_row_its_view_expects(attributed):
    items, _, _, _ = _generate()
    transform, cloze, statement, choice = items

    # Umformung: Freitext, keine Optionen.
    assert transform["front"] == "Der Server speichert die Messwerte."
    assert transform["back"] == "Die Messwerte werden vom Server gespeichert."
    assert "options" not in transform

    # Lücke: der Satz mit ___ steht vorne, die Lösung hinten.
    assert "___" in cloze["front"]
    assert cloze["back"] == "werden"
    assert "options" not in cloze

    # Richtig/Falsch: zwei feste Optionen, nicht vom Modell benannt.
    assert statement["options"] == ["Richtig", "Falsch"]
    assert statement["correct_idx"] == 0

    # Ankreuzen: Aufgabenzeile und Satz in front, vier Optionen.
    assert choice["front"].startswith("**Bilden Sie das Passiv.**")
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
    """Die Umformung braucht ein Muster, sonst weiss der Lernende nicht wohin. Eine
    Richtig/Falsch-Aufgabe folgt keinem Muster, dort waere es nur Ballast."""
    items, _, _, _ = _generate()
    assert items[0]["extras"]["pattern_front"] == _TOPIC["example"]["before"]
    assert items[0]["extras"]["pattern_back"] == _TOPIC["example"]["after"]
    for item in items[1:]:
        assert not item.get("extras")


def test_the_set_carries_no_header_anymore(attributed):
    # Ein gemischtes Set hat kein gemeinsames Muster mehr, das ueber allem stehen
    # koennte. Das Muster gehoert an die Aufgabe, die eines braucht.
    _, _, header, _ = _generate()
    assert header == {}


_GOOD_FOUR = [
    {"kind": "transform", "before": "Der Server speichert die Messwerte.",
     "after": "Die Messwerte werden vom Server gespeichert."},
    {"kind": "cloze", "sentence": "Die Messwerte ___ vom Server gespeichert.",
     "answer": "werden"},
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
    {"kind": "cloze", "sentence": "Ohne Lücke geht es nicht.", "answer": "x"},
    {"kind": "statement", "statement": "Zu kurz", "answer": True},
    {"kind": "choice", "task": "T", "sentence": "Der Server speichert Werte.",
     "options": ["a", "a", "b", "c"], "correct_idx": 0},
]


def test_an_unusable_item_of_any_kind_is_dropped(attributed):
    """Jedes Format hat seinen eigenen Filter. Hier faellt aus jedem genau einer
    durch, und die vier brauchbaren bleiben."""
    response = json.dumps({"title": "T", "exercises": _BAD_FOUR + _GOOD_FOUR})
    items, _, _, _ = _generate(response, count=8)
    assert len(items) == 4
    assert [i["front"] for i in items][0] == "Der Server speichert die Messwerte."


def test_a_run_where_most_items_fail_is_discarded_entirely(attributed):
    """Die bestehende Mindestquote gilt weiter, jetzt ueber alle vier Formate. Lieber
    ein fehlgeschlagenes Set als eine Uebung, in der die Haelfte unloesbar ist."""
    response = json.dumps({"title": "T", "exercises": _BAD_FOUR + _GOOD_FOUR[:1]})
    items, title, header, _ = _generate(response, count=5)
    assert items == []
    assert title == ""
    assert header == {}


def test_an_unknown_kind_is_dropped_rather_than_guessed(attributed):
    response = json.dumps({"title": "T", "exercises": [
        {"kind": "wortschatz", "before": "a b c.", "after": "c b a."},
        {"kind": "transform", "before": "Der Server speichert die Messwerte.",
         "after": "Die Messwerte werden vom Server gespeichert."},
    ]})
    items, _, _, _ = _generate(response, count=2)
    assert len(items) == 1


# ─── Der Plan ────────────────────────────────────────────────────────────────

def test_the_plan_fills_exactly_the_requested_count():
    for count in (1, 4, 5, 10, 15, 20):
        assert len(item_plan(count)) == count


def test_twelve_items_split_evenly_across_the_four_formats():
    plan = item_plan(12)
    for kind in KINDS:
        assert plan.count(kind) == 3


def test_a_count_that_does_not_divide_gives_the_front_formats_one_more():
    """Bei 5 Aufgaben geht es nicht glatt auf. Reihum heisst: die vorderen Formate
    bekommen einen mehr, und die Reihenfolge in KINDS ist damit eine Entscheidung
    und keine Nebensache."""
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
    # Richtig/Falsch beurteilt eine Aussage. Eine Frage hat keinen Wahrheitswert.
    assert not is_usable_statement("Ist das korrektes Passiv?", True)


# ─── Lückentext ──────────────────────────────────────────────────────────────

def test_a_gap_sentence_needs_a_gap_and_an_answer():
    assert is_usable_cloze("Das Buch ___ Dozentin ist interessant.", "der")


def test_a_sentence_without_a_gap_is_dropped():
    assert not is_usable_cloze("Das Buch der Dozentin ist interessant.", "der")


def test_a_gap_without_an_answer_is_dropped():
    assert not is_usable_cloze("Das Buch ___ Dozentin ist interessant.", "  ")


def test_an_answer_that_already_stands_in_the_sentence_is_dropped():
    """Sonst liest der Lernende die Lösung im Aufgabentext ab. Genau das macht das
    Modell gern, wenn das gesuchte Wort im Satz noch einmal vorkommt."""
    assert not is_usable_cloze("Der Titel ___ Buches steht der Titel.", "der Titel")


def test_a_gap_that_swallows_the_whole_sentence_is_dropped():
    # Nur eine Lücke und sonst nichts ist keine Aufgabe, sondern ein leeres Feld.
    assert not is_usable_cloze("___", "irgendwas")


# ─── Die beiden übernommenen Filter laufen weiter ────────────────────────────

def test_the_free_text_filter_still_rejects_a_question():
    assert not is_usable_pair("Was bedeutet das?", "Etwas.")


def test_the_choice_filter_still_rejects_four_content_options():
    # Vier verschiedene Inhalte statt vier Formen. Der Fehler, für den der
    # Wortüberdeckungs-Filter gebaut wurde.
    assert not is_usable_choice(
        "Welche Gerichte wurden gekocht?", "Am Samstag wurde gekocht.",
        ["Pizza und Pasta", "Tacos und Fajitas", "Sushi und Tempura", "Suppe und Salat"],
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
