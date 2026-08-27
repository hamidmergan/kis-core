"""The instruction is worded by the model, the template puts the name after a colon."""

import pytest

from src.features.ai_assistant.tasks.language_training._source_grammar import task_line
from src.services.aia_grammar_topic import TASK_KINDS, usable_task_lines


# The four reported names plus the eight from the seed.
_ECHTE_NAMEN = [
    "Relativsatz", "Adjektivdeklination ohne Artikel", "tekamolo",
    "Finalsätze Nominalstil Verbalstil",
    "Passiv Präsens", "Passiv mit Modalverb", "Perfekt", "Präteritum",
    "Konjunktiv II", "Relativsätze", "Nebensätze", "Adjektivdeklination",
]


_EIGENE = {
    "transform": "Forme den Satz in einen Nebensatz um.",
    "cloze": "Ergänze das fehlende Wort im Nebensatz.",
    "statement": "Ist der Nebensatz richtig gebildet?",
    "choice": "Welcher Nebensatz ist richtig gebildet?",
}


# --- the elaborated lines take precedence -------------------------------------

@pytest.mark.parametrize("kind", TASK_KINDS)
def test_the_written_line_wins_over_the_frame(kind):
    # Verbatim, whatever was elaborated goes to the learner unchanged.
    assert task_line(kind, "de", "Nebensätze", _EIGENE) == _EIGENE[kind]


def test_the_frame_no_longer_produces_the_broken_sentence():
    kaputt = "Setze den Satz ins Nebensätze."
    assert task_line("transform", "de", "Nebensätze", _EIGENE) != kaputt


# --- without them the template applies ----------------------------------------

def test_a_topic_from_before_this_field_still_gets_an_instruction():
    """Old topics have no lines of their own, then the sober template applies."""
    erwartet = "Forme den Satz nach dem Beispiel um. Zielform: Perfekt."
    assert task_line("transform", "de", "Perfekt") == erwartet
    assert task_line("transform", "de", "Perfekt", {}) == erwartet
    assert task_line("transform", "de", "Perfekt", None) == erwartet


def test_an_empty_line_falls_back_rather_than_showing_nothing():
    assert task_line("cloze", "de", "Perfekt", {"cloze": "   "}) == \
        "Ergänze das fehlende Wort. Zielform: Perfekt."


# --- the template can no longer go wrong --------------------------------------

@pytest.mark.parametrize("name", _ECHTE_NAMEN)
@pytest.mark.parametrize("kind", TASK_KINDS)
def test_the_frame_never_bends_a_name_it_cannot_bend(kind, name):
    """The topic name stands after a colon and never after a preposition."""
    zeile = task_line(kind, "de", name)
    assert f"ins {name}" not in zeile
    assert f": {name}." in zeile


@pytest.mark.parametrize("name", _ECHTE_NAMEN)
def test_the_reported_wording_is_gone_for_every_real_topic(name):
    assert "Setze den Satz ins" not in task_line("transform", "de", name)


# --- what passes as usable ----------------------------------------------------

def test_all_four_kinds_or_none():
    """All or nothing, three of four lines falls out of tune."""
    assert usable_task_lines(_EIGENE) == _EIGENE
    unvollstaendig = {k: v for k, v in _EIGENE.items() if k != "choice"}
    assert usable_task_lines(unvollstaendig) == {}


def test_a_one_word_line_is_not_an_instruction():
    # The topic name alone is not enough, it already stands above the set.
    knapp = dict(_EIGENE, transform="Nebensätze")
    assert usable_task_lines(knapp) == {}


@pytest.mark.parametrize("murks", [None, "", [], {"transform": "Forme den Satz um."}, 42])
def test_anything_unusable_falls_back_to_the_frame(murks):
    assert usable_task_lines(murks) == {}


def test_whitespace_is_trimmed():
    gepolstert = {k: f"  {v}  " for k, v in _EIGENE.items()}
    assert usable_task_lines(gepolstert) == _EIGENE


# The reference to the pattern sits in the sentence and is not appended.

def test_the_transform_line_points_at_the_worked_pair():
    assert task_line("transform", "de", "Perfekt") == \
        "Forme den Satz nach dem Beispiel um. Zielform: Perfekt."
    assert task_line("transform", "en", "Perfect") == \
        "Rewrite the sentence following the example. Target form: Perfect."


@pytest.mark.parametrize("formuliert", [
    # The reference is recorded, in the place where it belongs.
    "Forme den Satz nach dem Beispiel in einen Relativsatz um.",
    # It may be missing where it does not fit.
    "Bilde den Satz nach der tekamolo-Regel.",
    "Forme den Satz in einen Satz mit Adjektivdeklination ohne Artikel um.",
])
def test_nothing_is_appended_to_a_written_transform_line(formuliert):
    eigene = dict(_EIGENE, transform=formuliert)
    assert task_line("transform", "de", "Relativsatz", eigene) == formuliert


@pytest.mark.parametrize("kind", ["cloze", "statement", "choice"])
def test_only_the_transform_card_carries_the_reference(kind):
    """A pattern only appears above the reshaping exercise."""
    assert "Beispiel" not in task_line(kind, "de", "Perfekt")
    assert "example" not in task_line(kind, "en", "Perfect")
