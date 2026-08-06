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


def _client_queue(*contents):
    """Fake-Client, der die Antworten der Reihe nach ausgibt. Die letzte wiederholt
    sich, damit ein Test nicht an der Anzahl der Würfe hängt."""
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
    {"kind": "cloze", "sentence": "Die Messwerte ___ vom Server gespeichert.",
     "answer": "werden", "options": ["werden", "wurden", "sind", "waren"],
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


# ─── Ein Set, vier Formate ───────────────────────────────────────────────────

def test_the_prompt_orders_the_formats_by_number(attributed):
    # Eine Absichtserklaerung wirkt nicht, eine Zahl wirkt.
    _, _, _, calls = _generate(count=12)
    system = calls[0][0]["content"]
    for kind in KINDS:
        assert f'3 of kind "{kind}"' in system


def test_every_item_starts_with_a_bold_instruction(attributed):
    """Ohne Anweisung ist auch ein Textfeld nutzlos: der Lernende sieht einen Satz
    und weiss nicht, ob er umformen, ergaenzen oder ankreuzen soll."""
    items, _, _, _ = _generate()
    for item in items:
        assert item["front"].startswith("**")
        assert "**\n\n" in item["front"]


def test_each_format_becomes_the_row_its_view_expects(attributed):
    items, _, _, _ = _generate()
    transform, cloze, statement, choice = items

    # Umformung: Freitext, keine Optionen.
    assert transform["front"].endswith("Der Server speichert die Messwerte.")
    assert transform["back"] == "Die Messwerte werden vom Server gespeichert."
    assert "options" not in transform

    # Lücke: der Satz mit ___ steht vorne, dazu vier Optionen zum Anklicken.
    assert "___" in cloze["front"]
    assert cloze["back"] == "werden"
    assert len(cloze["options"]) == 4
    assert cloze["correct_idx"] == 0

    # Richtig/Falsch: zwei feste Optionen, nicht vom Modell benannt.
    assert statement["options"] == ["Richtig", "Falsch"]
    assert statement["correct_idx"] == 0

    # Ankreuzen: Aufgabenzeile in front, vier Optionen.
    assert choice["front"].startswith("**Welcher Satz steht korrekt im Passiv Präsens?**")
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
     "answer": "werden", "options": ["werden", "wurden", "sind", "waren"],
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
    assert items[0]["front"].endswith("Der Server speichert die Messwerte.")


def test_a_run_where_most_items_fail_is_discarded_entirely(attributed):
    """Die bestehende Mindestquote gilt weiter, jetzt ueber alle vier Formate. Lieber
    ein fehlgeschlagenes Set als eine Uebung, in der die Haelfte unloesbar ist."""
    response = json.dumps({"title": "T", "exercises": _BAD_FOUR + _GOOD_FOUR[:1]})
    items, title, header, _ = _generate(response, count=5)
    assert items == []
    assert title == ""
    assert header == {}


def test_the_prompt_demands_full_sentences_as_options(attributed):
    """Am laufenden System aufgefallen: das Modell lieferte als Optionen einzelne
    Wortformen ("geschrieben", "schreiben", "schreibt"). Der Wortüberdeckungs-Filter
    misst Überdeckung in Wörtern und sieht bei Einzelwörtern null, also fiel JEDE
    Ankreuz-Aufgabe durch und das Set kam ohne dieses Format heraus.

    Der Filter ist richtig, er trennt Form von Inhalt. Also muss die Vorgabe die
    Form nennen, die er erwartet."""
    _, _, _, calls = _generate()
    system = calls[0][0]["content"]
    assert "complete sentence" in system.lower()


def test_the_same_sentence_never_appears_twice(attributed):
    """Ebenfalls am laufenden System aufgefallen: derselbe Satz kam an Position 1
    und 5. Zweimal dieselbe Aufgabe ist verlorene Übungszeit."""
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
    """Gemeldet: 10 bestellt, 7 bekommen. Die Filter werfen weg, aber nichts füllte
    wieder auf. Ein zweiter Wurf holt die fehlenden nach, mehr nicht: das
    Anfragen-Kontingent teilt sich die ganze Hochschule."""
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
    """Sonst kippt die Mischung. Gemessen: bei 10 bestellten Aufgaben kamen 5 mit
    vier Optionen heraus statt der geplanten 5 auf zwei Formate verteilt. Der
    Nachschlag lieferte, was dem Modell am leichtesten faellt, naemlich Ankreuzen."""
    only_transforms = json.dumps({"title": "T", "exercises": [
        {"kind": "transform", "before": f"Das Team prüft die Quelle {i} genau.",
         "after": f"Die Quelle {i} wird vom Team genau geprüft."} for i in range(4)
    ]})
    client, calls = _client_queue(only_transforms)
    generate_grammar_from_source(client, "m", _ctx(), _TOPIC, 8, locale="de")

    zweiter = calls[1][0]["content"]
    # Umformungen sind voll, danach darf nicht mehr gefragt werden.
    assert 'of kind "transform"' not in zweiter
    for kind in ("cloze", "statement", "choice"):
        assert f'of kind "{kind}"' in zweiter


def test_a_surplus_of_one_format_is_capped_at_the_plan(attributed):
    """Der erste Wurf liefert oft mehr Umformungen als geplant. Ohne Deckel landen
    alle im Set und die Mischung kippt schon vor dem ersten Nachschlag.

    Hier liefert Wurf 1 acht Umformungen und Wurf 2 die fehlenden Arten. Am Ende
    duerfen nur die geplanten zwei Umformungen drin sein."""
    many = json.dumps({"title": "T", "exercises": [
        {"kind": "transform", "before": f"Das Team prüft die Quelle {i} genau.",
         "after": f"Die Quelle {i} wird vom Team genau geprüft."} for i in range(8)
    ]})
    rest = json.dumps({"title": "T", "exercises": [
        {"kind": "cloze", "sentence": f"Die Quelle {i} ___ vom Team geprüft.",
         "answer": "wird", "options": ["wird", "werden", "wurde", "ist"],
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
    umformungen = [i for i in items if "Setze den Satz" in i["front"]]
    assert len(umformungen) == 2
    assert len(items) == 8


def test_the_last_draw_fills_up_with_whatever_it_gets(attributed):
    """Am Ende zaehlt die Anzahl mehr als die Mischung. Wer zehn bestellt, will zehn,
    auch wenn das Modell partout kein Ankreuzen liefert."""
    many = json.dumps({"title": "T", "exercises": [
        {"kind": "transform", "before": f"Das Team prüft die Quelle {i} genau.",
         "after": f"Die Quelle {i} wird vom Team genau geprüft."} for i in range(8)
    ]})
    client, _ = _client_queue(many)
    items, _, _ = generate_grammar_from_source(
        client, "m", _ctx(), _TOPIC, 8, locale="de")
    assert len(items) == 8


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
    """Am laufenden System gesehen: Aufgabe 1 war derselbe Satz wie das Muster, das
    direkt darunter mit der Lösung stand. Der Lernende musste nur abschreiben.

    Frueher fiel das nicht auf, weil das Muster einmal ueber dem ganzen Set stand.
    Jetzt haengt es an der Aufgabe, also stehen beide uebereinander."""
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
    # Auch als Lueckensatz oder Ankreuz-Satz waere es der Musterssatz.
    ex = _TOPIC["example"]
    response = json.dumps({"title": "T", "exercises": [
        {"kind": "cloze", "sentence": ex["before"].replace("erklärt", "___"),
         "answer": "erklärt"},
        {"kind": "transform", "before": "Das Team schreibt den Bericht.",
         "after": "Der Bericht wird vom Team geschrieben."},
    ]})
    items, _, _, _ = _generate(response, count=2)
    assert len(items) == 1


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

_GAP_OPTIONS = ["der", "des", "dem", "den"]


def test_a_gap_sentence_needs_a_gap_an_answer_and_four_options():
    """Als Freitext war die Luecke zu schwer: bei "Die Arbeit wird von der Dozentin
    ___." kann man alles Moegliche schreiben, und der Lernende raet. Mit vier
    Optionen ist die Aufgabe loesbar und trotzdem eine Formentscheidung."""
    assert is_usable_cloze("Das Buch ___ Dozentin ist interessant.", "der", _GAP_OPTIONS, 0)


def test_a_gap_without_options_is_dropped():
    assert not is_usable_cloze("Das Buch ___ Dozentin ist interessant.", "der", [], None)


def test_a_gap_needs_exactly_four_options():
    assert not is_usable_cloze("Das Buch ___ ist da.", "der", ["der", "des"], 0)


def test_two_identical_options_drop_the_gap():
    # Zweimal dieselbe Antwort: der Lernende kann recht haben und falsch liegen.
    assert not is_usable_cloze("Das Buch ___ ist da.", "der", ["der", "der", "des", "dem"], 0)


def test_the_marked_option_must_be_the_answer():
    assert not is_usable_cloze("Das Buch ___ ist da.", "der", _GAP_OPTIONS, 1)


def test_gap_options_may_be_single_words():
    """Hier gilt der Wortueberdeckungs-Filter des Ankreuzens ausdruecklich NICHT.
    In eine Luecke gehoert ein Wort, keine Satzvariante."""
    assert is_usable_cloze("Der Bericht ___ geschrieben.", "wird",
                           ["wird", "werden", "wurde", "ist"], 0)


def test_a_sentence_without_a_gap_is_dropped():
    assert not is_usable_cloze("Das Buch der Dozentin ist interessant.", "der", _GAP_OPTIONS, 0)


def test_a_gap_without_an_answer_is_dropped():
    assert not is_usable_cloze("Das Buch ___ Dozentin ist interessant.", "  ", _GAP_OPTIONS, 0)


def test_an_answer_that_already_stands_in_the_sentence_is_dropped():
    """Sonst liest der Lernende die Lösung im Aufgabentext ab. Genau das macht das
    Modell gern, wenn das gesuchte Wort im Satz noch einmal vorkommt."""
    assert not is_usable_cloze("Der Titel ___ Buches steht der Titel.", "der Titel",
                            ["der Titel", "des Titels", "dem Titel", "den Titel"], 0)


def test_a_gap_that_swallows_the_whole_sentence_is_dropped():
    # Nur eine Lücke und sonst nichts ist keine Aufgabe, sondern ein leeres Feld.
    assert not is_usable_cloze("___", "irgendwas", ["irgendwas", "b", "c", "d"], 0)


def test_a_gap_hung_behind_a_finished_sentence_is_dropped():
    """Am laufenden System gemeldet: der Satz war fertig und die Lücke hing hinten
    dran. Da fehlt nichts, es gibt nichts zu füllen, und der Lernende raet."""
    assert not is_usable_cloze(
        "Die Literatur wird von den Studierenden recherchiert. ___", "wird",
        ["wird", "werden", "wurde", "ist"], 0)


def test_a_gap_at_the_end_but_inside_the_sentence_is_fine():
    # Die Lücke darf am Satzende stehen, solange der Punkt DAHINTER kommt.
    assert is_usable_cloze("Die Arbeit wird von der Dozentin ___.", "korrigiert",
                        ["korrigiert", "korrigieren", "korrigierte", "korrigiert hat"], 0)


@pytest.mark.parametrize("mark", [".", "!", "?", "…"])
def test_no_sentence_end_may_stand_directly_before_the_gap(mark):
    assert not is_usable_cloze(f"Der Bericht ist fertig{mark} ___", "wirklich",
                            ["wirklich", "sehr", "ganz", "kaum"], 0)


# ─── Die Anweisung an der Aufgabe ────────────────────────────────────────────

def test_every_item_carries_its_own_task_line():
    """Der gemeldete Fall: ein nackter Satz ohne Anweisung. Auch mit Textfeld weiss
    niemand, ob umgeformt, ergänzt oder angekreuzt werden soll. Frueher stand die
    Anweisung einmal ueber dem Set, ein gemischtes Set hat aber keine gemeinsame."""
    from src.features.ai_assistant.tasks.language_training._source_grammar import task_line
    for kind in KINDS:
        assert task_line(kind, "de", "Passiv Präsens").strip()
        assert task_line(kind, "en", "Passive present").strip()


@pytest.mark.parametrize("kind", KINDS)
def test_every_task_line_names_the_target_form(kind):
    """Gemeldet: "Wähle die richtige Form." Form für was? Ohne die Zielform im Text
    weiss der Lernende nicht, worauf er achten soll."""
    from src.features.ai_assistant.tasks.language_training._source_grammar import task_line
    assert "Passiv Präsens" in task_line(kind, "de", "Passiv Präsens")
    assert "Passive present" in task_line(kind, "en", "Passive present")


def test_a_choice_that_asks_which_is_correct_does_not_repeat_the_sentence(attributed):
    """Steht der Satz oben UND als richtige Option darunter, liest man ihn zweimal.
    Bei dieser Bauart traegt die Frage alles Noetige, der Satz ist Ballast."""
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
    # Andere Bauart: der Satz ist die Vorlage und wird gebraucht.
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


def test_the_sentence_may_be_the_correct_option():
    """Das Modell baut die Aufgabe oft als "welche Form ist richtig?" und stellt den
    Satz selbst als richtige Option hinein. Das ist eine legitime Bauart, und mein
    Filter hat sie bis zum 2026-08-05 verworfen. Dadurch fehlten Aufgaben im Set."""
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
    """Andersherum bleibt es ein Verrat: steht der Satz als falsche Option da, ist
    die Aufgabe "streiche das, was du schon liest"."""
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
