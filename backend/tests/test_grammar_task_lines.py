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
    # Beim Umformen kommt der Verweis auf das Muster dazu, der formulierte Satz
    # selbst bleibt aber vorn stehen.
    assert task_line(kind, "de", "Nebensätze", _EIGENE).startswith(
        _EIGENE[kind].rstrip(".?"))


def test_the_frame_no_longer_produces_the_broken_sentence():
    kaputt = "Setze den Satz ins Nebensätze."
    assert task_line("transform", "de", "Nebensätze", _EIGENE) != kaputt


# --- ohne sie bleibt es bei der Schablone -------------------------------------

def test_a_topic_from_before_this_field_still_gets_an_instruction():
    """Alte Themen haben keine eigenen Zeilen. Eine schiefe Anweisung ist immer noch
    besser als ein nackter Satz, bei dem der Lernende nicht weiss, was zu tun ist."""
    erwartet = "Setze den Satz ins Perfekt, nach dem Beispiel."
    assert task_line("transform", "de", "Perfekt") == erwartet
    assert task_line("transform", "de", "Perfekt", {}) == erwartet
    assert task_line("transform", "de", "Perfekt", None) == erwartet


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


# --- der Verweis auf das Muster -----------------------------------------------
#
# Eine Umformung hat oft mehr als eine richtige Fassung: "Der Bericht wird
# geschrieben." und "Der Bericht wird vom Team geschrieben." sind beide Passiv. Über
# der Aufgabe steht ein gelöstes Musterpaar, das zeigt, welche Fassung gemeint ist,
# aber die Anweisung zeigte bisher nicht darauf.

def test_the_transform_line_points_at_the_worked_pair():
    assert task_line("transform", "de", "Perfekt") == \
        "Setze den Satz ins Perfekt, nach dem Beispiel."
    assert task_line("transform", "en", "Perfect") == \
        "Rewrite the sentence in the Perfect, following the example."


def test_the_written_transform_line_gets_the_reference_too():
    """Der Verweis wird angehängt und steht nicht in der Schablone.

    Die Schablone ist nur der Rückfall. Die Themen, die es schon gibt, tragen ihre
    formulierte Zeile in der Datenbank, und die bekäme den Verweis sonst nie.
    """
    assert task_line("transform", "de", "Nebensätze", _EIGENE) == \
        "Forme den Satz in einen Nebensatz um, nach dem Beispiel."


@pytest.mark.parametrize("schon_drin", [
    "Forme den Satz nach dem Beispiel um.",
    # Frei formuliert: das Modell hält sich an keine feste Wendung.
    "Forme den Satz um, wie im Beispiel.",
    "Rewrite the sentence as in the example.",
])
def test_the_reference_is_not_doubled(schon_drin):
    eigene = dict(_EIGENE, transform=schon_drin)
    assert task_line("transform", "de", "Nebensätze", eigene) == schon_drin


@pytest.mark.parametrize("kind", ["cloze", "statement", "choice"])
def test_only_the_transform_card_carries_the_reference(kind):
    """Ein Muster steht nur über der Umform-Aufgabe.

    Bei Lücke, Richtig/Falsch und Ankreuzen zeigte der Verweis auf nichts, und dort
    gibt es auch nichts zu entscheiden: angeklickt wird eine von vier Antworten.
    """
    assert "Beispiel" not in task_line(kind, "de", "Perfekt")
    assert "Beispiel" not in task_line(kind, "de", "Nebensätze", _EIGENE)
    assert "example" not in task_line(kind, "en", "Perfect")
