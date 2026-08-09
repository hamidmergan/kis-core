"""Die Anweisung über einer Grammatik-Aufgabe wird formuliert, nicht zusammengesteckt.

Die alte Schablone setzte den Themennamen ungebeugt ein:

    "Setze den Satz ins {form}."

Das trifft nur sächliche Einzahlwörter. An den acht echten Themen eines Kursraums
gemessen ging die Hälfte auf:

    Passiv Präsens, Konjunktiv II, Perfekt, Präteritum   -> richtig
    Nebensätze, Relativsätze, Adjektivdeklination, ...   -> "Setze den Satz ins Nebensätze."

Beugung lässt sich nicht schablonisieren, und eine deutsche Grammatikregel im Code bräche
bei der nächsten Hochschule. Deshalb formuliert das Modell die vier Zeilen einmal beim
Ausarbeiten des Themas mit, und sie werden am Thema gespeichert.
"""

import pytest

from src.features.ai_assistant.tasks.language_training._source_grammar import task_line
from src.services.aia_grammar_topic import TASK_KINDS, usable_task_lines


_EIGENE = {
    "transform": "Forme den Satz in einen Nebensatz um.",
    "cloze": "Ergänze das fehlende Wort im Nebensatz.",
    "statement": "Ist der Nebensatz richtig gebildet?",
    "choice": "Welcher Nebensatz ist richtig gebildet?",
}


# --- die ausgearbeiteten Zeilen haben Vorrang ---------------------------------

@pytest.mark.parametrize("kind", TASK_KINDS)
def test_the_written_line_wins_over_the_frame(kind):
    assert task_line(kind, "de", "Nebensätze", _EIGENE) == _EIGENE[kind]


def test_the_frame_no_longer_produces_the_broken_sentence():
    kaputt = "Setze den Satz ins Nebensätze."
    assert task_line("transform", "de", "Nebensätze", _EIGENE) != kaputt


# --- ohne sie bleibt es bei der Schablone -------------------------------------

def test_a_topic_from_before_this_field_still_gets_an_instruction():
    """Alte Themen haben keine eigenen Zeilen. Eine schiefe Anweisung ist immer noch
    besser als ein nackter Satz, bei dem der Lernende nicht weiss, was zu tun ist."""
    assert task_line("transform", "de", "Perfekt") == "Setze den Satz ins Perfekt."
    assert task_line("transform", "de", "Perfekt", {}) == "Setze den Satz ins Perfekt."
    assert task_line("transform", "de", "Perfekt", None) == "Setze den Satz ins Perfekt."


def test_an_empty_line_falls_back_rather_than_showing_nothing():
    assert task_line("cloze", "de", "Perfekt", {"cloze": "   "}) == \
        "Ergänze das fehlende Wort im Perfekt."


# --- was als brauchbar durchgeht ----------------------------------------------

def test_all_four_kinds_or_none():
    """Alles oder nichts.

    Mit drei von vier Zeilen hätte ein gemischtes Set eine Aufgabe mit formulierter
    Anweisung und drei mit Schablone, und die eine fiele aus dem Ton.
    """
    assert usable_task_lines(_EIGENE) == _EIGENE
    unvollstaendig = {k: v for k, v in _EIGENE.items() if k != "choice"}
    assert usable_task_lines(unvollstaendig) == {}


def test_a_one_word_line_is_not_an_instruction():
    # Der Themenname allein reicht nicht, der steht ohnehin schon über dem Set.
    knapp = dict(_EIGENE, transform="Nebensätze")
    assert usable_task_lines(knapp) == {}


@pytest.mark.parametrize("murks", [None, "", [], {"transform": "Forme den Satz um."}, 42])
def test_anything_unusable_falls_back_to_the_frame(murks):
    assert usable_task_lines(murks) == {}


def test_whitespace_is_trimmed():
    gepolstert = {k: f"  {v}  " for k, v in _EIGENE.items()}
    assert usable_task_lines(gepolstert) == _EIGENE
