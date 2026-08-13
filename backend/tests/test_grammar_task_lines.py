"""Die Anweisung über einer Grammatik-Aufgabe wird formuliert, nicht zusammengesteckt.

Die alte Schablone setzte den Themennamen ungebeugt hinter eine Präposition:

    "Setze den Satz ins {form}."

Das trifft nur sächliche Einzahlwörter. An den acht echten Themen eines Kursraums
gemessen ging die Hälfte auf:

    Passiv Präsens, Konjunktiv II, Perfekt, Präteritum   -> richtig
    Nebensätze, Relativsätze, Adjektivdeklination, ...   -> "Setze den Satz ins Nebensätze."

Beugung lässt sich nicht schablonisieren, und eine deutsche Grammatikregel im Code bräche
bei der nächsten Hochschule. Deshalb formuliert das Modell die vier Zeilen einmal beim
Ausarbeiten des Themas mit, und sie werden am Thema gespeichert.

Am 2026-08-12 hat das Sprachenzentrum vier Meldungen dazu geschickt. Sie zeigen, dass
die Schablone auch mit richtiger Beugung nicht zu retten ist:

    "Setze den Satz ins Relativsatz"          -> männlich, "ins" passt nicht
    "Setze den Satz ins Adjektivdeklination"  -> weiblich, dazu keine Satzform
    "Setze den Satz ins tekamolo"             -> eine Stellungsregel, kein Behälter
    "Setze den Satz ins Finalsätze Nominalstil Verbalstil" -> drei Themen in einem Namen

Deshalb steht der Name in der Schablone jetzt hinter einem Doppelpunkt und nicht mehr
hinter einer Präposition. So kann sie in keiner Sprache falsch werden, egal was der
Dozent tippt. Der schöne Satz kommt vom Modell.
"""

import pytest

from src.features.ai_assistant.tasks.language_training._source_grammar import task_line
from src.services.aia_grammar_topic import TASK_KINDS, usable_task_lines


# Die vier gemeldeten Themennamen plus die acht Namen aus dem Grundstock. Jeder von
# ihnen muss durch die Schablone gehen, ohne einen schiefen Satz zu ergeben.
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


# --- die ausgearbeiteten Zeilen haben Vorrang ---------------------------------

@pytest.mark.parametrize("kind", TASK_KINDS)
def test_the_written_line_wins_over_the_frame(kind):
    # Wortwörtlich. Was ausgearbeitet wurde, geht unverändert an den Lernenden.
    assert task_line(kind, "de", "Nebensätze", _EIGENE) == _EIGENE[kind]


def test_the_frame_no_longer_produces_the_broken_sentence():
    kaputt = "Setze den Satz ins Nebensätze."
    assert task_line("transform", "de", "Nebensätze", _EIGENE) != kaputt


# --- ohne sie bleibt es bei der Schablone -------------------------------------

def test_a_topic_from_before_this_field_still_gets_an_instruction():
    """Alte Themen haben keine eigenen Zeilen. Eine nüchterne Anweisung ist immer noch
    besser als ein nackter Satz, bei dem der Lernende nicht weiss, was zu tun ist."""
    erwartet = "Forme den Satz nach dem Beispiel um. Zielform: Perfekt."
    assert task_line("transform", "de", "Perfekt") == erwartet
    assert task_line("transform", "de", "Perfekt", {}) == erwartet
    assert task_line("transform", "de", "Perfekt", None) == erwartet


def test_an_empty_line_falls_back_rather_than_showing_nothing():
    assert task_line("cloze", "de", "Perfekt", {"cloze": "   "}) == \
        "Ergänze das fehlende Wort. Zielform: Perfekt."


# --- die Schablone kann nicht mehr schief werden ------------------------------

@pytest.mark.parametrize("name", _ECHTE_NAMEN)
@pytest.mark.parametrize("kind", TASK_KINDS)
def test_the_frame_never_bends_a_name_it_cannot_bend(kind, name):
    """Der Themenname steht hinter einem Doppelpunkt und nie hinter "ins".

    Beugen kann die Schablone nicht, also lässt sie es. Ein Doppelpunkt braucht kein
    Geschlecht, keine Zahl und keinen Fall, und er stimmt damit auch für "tekamolo",
    das gar keine Form ist, in die man einen Satz setzen könnte.
    """
    zeile = task_line(kind, "de", name)
    assert f"ins {name}" not in zeile
    assert f": {name}." in zeile


@pytest.mark.parametrize("name", _ECHTE_NAMEN)
def test_the_reported_wording_is_gone_for_every_real_topic(name):
    assert "Setze den Satz ins" not in task_line("transform", "de", name)


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
# und die Umform-Anweisung zeigt darauf.
#
# Er steht IM Satz und wird nicht angehängt. Angehängt ergab er genau die am
# 2026-08-12 gemeldete Zeile ("..., nach dem Beispiel."), und hinter einem frei
# formulierten Satz liest sich das immer schief: "Bilde den Satz nach der
# tekamolo-Regel, nach dem Beispiel."

def test_the_transform_line_points_at_the_worked_pair():
    assert task_line("transform", "de", "Perfekt") == \
        "Forme den Satz nach dem Beispiel um. Zielform: Perfekt."
    assert task_line("transform", "en", "Perfect") == \
        "Rewrite the sentence following the example. Target form: Perfect."


@pytest.mark.parametrize("formuliert", [
    # Der Verweis ist mitgeschrieben, an der Stelle, an der er hingehört.
    "Forme den Satz nach dem Beispiel in einen Relativsatz um.",
    # Und er darf fehlen, wo er nicht hinpasst. "Bilde den Satz nach der
    # tekamolo-Regel, nach dem Beispiel." wäre schlechter als ohne.
    "Bilde den Satz nach der tekamolo-Regel.",
    "Forme den Satz in einen Satz mit Adjektivdeklination ohne Artikel um.",
])
def test_nothing_is_appended_to_a_written_transform_line(formuliert):
    eigene = dict(_EIGENE, transform=formuliert)
    assert task_line("transform", "de", "Relativsatz", eigene) == formuliert


@pytest.mark.parametrize("kind", ["cloze", "statement", "choice"])
def test_only_the_transform_card_carries_the_reference(kind):
    """Ein Muster steht nur über der Umform-Aufgabe.

    Bei Lücke, Richtig/Falsch und Ankreuzen zeigte der Verweis auf nichts, und dort
    gibt es auch nichts zu entscheiden: angeklickt wird eine von vier Antworten.
    """
    assert "Beispiel" not in task_line(kind, "de", "Perfekt")
    assert "example" not in task_line(kind, "en", "Perfect")
