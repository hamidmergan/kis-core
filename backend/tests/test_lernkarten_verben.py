"""Verbangaben auf der Lernkarte.

Ein Nomen zeigt seit jeher Singular und Plural. Ein Verb zeigt jetzt seine Art in
Klammern hinter der Wortart und darunter Präsens, Präteritum und Perfekt.

Geprüft wird der Weg vom Modell nach ``extras``: die Ansicht liest genau diese
Schlüssel, und ein leeres Feld darf keine leere Zeile erzeugen. Dazu die Regeln im
Prompt, die am meisten wehtun, wenn sie jemand später herausstreicht: das Hilfsverb
im Perfekt und das Verbot zu raten.
"""

import json
import types

from src.features.ai_assistant.tasks.language_training._glossary import _generate_flashcards
from src.features.ai_assistant.tasks.language_training._source_flashcards import (
    _format_lernkarte,
    AIA_FLASHCARD_EXTRAS_FIELDS,
)
from src.tool_prompts import AIA_LERNKARTEN_PROMPT


def _fake_client(content: str):
    """Modell-Ersatz: liefert immer dieselbe Antwort, kein Netz, keine Datenbank."""
    def create(model, messages, **kwargs):
        message = types.SimpleNamespace(content=content)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])

    return types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
    )


# --- der Weg nach extras -----------------------------------------------------

def test_verbformen_landen_in_extras():
    item = _format_lernkarte({
        "begriff": "sich treffen",
        "definition": "Mit einer anderen Person an einem Ort zusammenkommen.",
        "word_class": "Verb (unregelmäßig, reflexiv)",
        "verb_present": "trifft sich",
        "verb_past": "traf sich",
        "verb_perfect": "hat sich getroffen",
    })
    assert item["extras"]["verb_present"] == "trifft sich"
    assert item["extras"]["verb_past"] == "traf sich"
    assert item["extras"]["verb_perfect"] == "hat sich getroffen"
    assert item["extras"]["word_class"] == "Verb (unregelmäßig, reflexiv)"


def test_leere_verbformen_erzeugen_keine_schluessel():
    """Ein Nomen liefert die Felder leer mit. Die Ansicht zeichnet eine Zeile, sobald
    der Schlüssel da ist, also darf er gar nicht erst entstehen."""
    item = _format_lernkarte({
        "begriff": "Fluchtweg",
        "definition": "Weg aus dem Gebäude nach draußen.",
        "word_class": "Nomen",
        "singular": "der Fluchtweg",
        "plural": "die Fluchtwege",
        "verb_present": "",
        "verb_past": "   ",
        "verb_perfect": None,
    })
    assert "verb_present" not in item["extras"]
    assert "verb_past" not in item["extras"]
    assert "verb_perfect" not in item["extras"]
    assert item["extras"]["plural"] == "die Fluchtwege"


def test_verbformen_werden_getrimmt():
    item = _format_lernkarte({
        "begriff": "lernen", "definition": "D", "verb_present": "  lernt  ",
    })
    assert item["extras"]["verb_present"] == "lernt"


def test_karte_ohne_verbfelder_bleibt_wie_vorher():
    """Alte Sätze und Modelle, die die Felder nicht kennen, ändern sich nicht."""
    item = _format_lernkarte({"begriff": "X", "definition": "Y"})
    assert item.get("extras") is None


# --- die Regeln im Prompt ----------------------------------------------------

def test_prompt_kennt_die_drei_felder():
    for feld in ("verb_present", "verb_past", "verb_perfect"):
        assert feld in AIA_LERNKARTEN_PROMPT


def test_prompt_verlangt_das_hilfsverb_im_perfekt():
    """Ohne hat oder ist ist die Perfektform für den Lernenden wertlos."""
    assert "hat sich getroffen" in AIA_LERNKARTEN_PROMPT
    assert "MUST carry its auxiliary" in AIA_LERNKARTEN_PROMPT


def test_prompt_verbietet_zu_raten():
    """Lieber eine fehlende Zeile als eine erfundene Form auf einer Lernkarte."""
    assert "leave ALL THREE empty" in AIA_LERNKARTEN_PROMPT


def test_prompt_haelt_die_formen_in_der_quellsprache():
    """Die Formen sind das Lernmaterial, sie werden nie in die Erklärsprache übersetzt."""
    assert (
        "the verb forms in 'verb_present', 'verb_past' and 'verb_perfect'"
        in AIA_LERNKARTEN_PROMPT
    )


def test_prompt_kennt_die_klammer_hinter_der_wortart():
    assert "Verb (unregelmäßig, reflexiv)" in AIA_LERNKARTEN_PROMPT


# --- gemeinsame Konstante für Quelltext und Glossar --------------------------

def test_gemeinsame_konstante_enthaelt_alle_felder():
    """Die gemeinsame Konstante AIA_FLASHCARD_EXTRAS_FIELDS ist für beide Wege
    (Quelltext und Glossar) maßgeblich und muss alle neuen Felder enthalten."""
    assert "verb_present" in AIA_FLASHCARD_EXTRAS_FIELDS
    assert "verb_past" in AIA_FLASHCARD_EXTRAS_FIELDS
    assert "verb_perfect" in AIA_FLASHCARD_EXTRAS_FIELDS
    # Und die etablierten Felder
    assert "word_parts" in AIA_FLASHCARD_EXTRAS_FIELDS
    assert "word_class" in AIA_FLASHCARD_EXTRAS_FIELDS
    assert "singular" in AIA_FLASHCARD_EXTRAS_FIELDS
    assert "plural" in AIA_FLASHCARD_EXTRAS_FIELDS


def test_glossar_verbformen_landen_in_extras():
    """Im Glossar-Weg legt _generate_flashcards Verbformen korrekt in extras ab.
    Der Test ruft _generate_flashcards wirklich auf, nicht nur _format_lernkarte."""
    # Modell-Antwort mit einem Verb mit allen drei Zeitformen
    antwort = json.dumps({"cards": [{
        "begriff": "schreiben",
        "definition": "Worte aufzeichnen.",
        "word_class": "Verb (unregelmäßig)",
        "verb_present": "schreibt",
        "verb_past": "schrieb",
        "verb_perfect": "hat geschrieben",
        "example_sentence": "Ich schreibe.",
    }]})
    client = _fake_client(antwort)
    glossary_entries = [{
        "term_de": "schreiben",
        "term_en": "write",
        "definition": "Worte aufzeichnen.",
        "filename": "Deutsch.pdf",
        "page_number": 5,
    }]

    items = _generate_flashcards(client, "modell", glossary_entries, "German")

    # Alle drei Verbformen müssen in extras landen
    assert items[0]["extras"]["verb_present"] == "schreibt"
    assert items[0]["extras"]["verb_past"] == "schrieb"
    assert items[0]["extras"]["verb_perfect"] == "hat geschrieben"
    # Auch die anderen Felder
    assert items[0]["extras"]["word_class"] == "Verb (unregelmäßig)"
    assert items[0]["extras"]["example_sentence"] == "Ich schreibe."


def test_glossar_leere_verbformen_erzeugen_keine_schluessel():
    """Im Glossar-Weg landen leere Verbformen nicht in extras, auch wenn das
    Modell sie mit leeren Werten liefert. Der Test ruft _generate_flashcards auf."""
    # Modell-Antwort mit einem Nomen (keine Verbformen)
    antwort = json.dumps({"cards": [{
        "begriff": "Metapher",
        "definition": "Ein Vergleich ohne 'wie'.",
        "word_class": "Nomen",
        "singular": "die Metapher",
        "plural": "die Metaphern",
        "verb_present": "",
        "verb_past": "",
        "verb_perfect": "",
    }]})
    client = _fake_client(antwort)
    glossary_entries = [{
        "term_de": "Metapher",
        "term_en": "metaphor",
        "definition": "Ein Vergleich ohne 'wie'.",
        "filename": "Deutsch.pdf",
        "page_number": 10,
    }]

    items = _generate_flashcards(client, "modell", glossary_entries, "German")

    # Leere Verbformen dürfen nicht in extras sein
    extras = items[0].get("extras", {})
    assert "verb_present" not in extras
    assert "verb_past" not in extras
    assert "verb_perfect" not in extras
    # Aber die etablierten Felder kommen durch
    assert extras["singular"] == "die Metapher"
    assert extras["plural"] == "die Metaphern"
    assert extras["word_class"] == "Nomen"
