"""Verbangaben auf der Lernkarte.

Ein Nomen zeigt seit jeher Singular und Plural. Ein Verb zeigt jetzt seine Art in
Klammern hinter der Wortart und darunter Präsens, Präteritum und Perfekt.

Geprüft wird der Weg vom Modell nach ``extras``: die Ansicht liest genau diese
Schlüssel, und ein leeres Feld darf keine leere Zeile erzeugen. Dazu die Regeln im
Prompt, die am meisten wehtun, wenn sie jemand später herausstreicht: das Hilfsverb
im Perfekt und das Verbot zu raten.
"""

from src.features.ai_assistant.tasks.language_training._source_flashcards import (
    _format_lernkarte,
    AIA_FLASHCARD_EXTRAS_FIELDS,
)
from src.tool_prompts import AIA_LERNKARTEN_PROMPT


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
    """Der Glossar-Weg _generate_flashcards benutzt dieselbe Konstante und legt
    Verbformen korrekt in extras ab."""
    # Simuliere eine Glossar-Antwort mit Verbformen
    glossar_card = {
        "begriff": "schreiben",
        "definition": "Worte auf Papier oder am Computer aufzeichnen.",
        "word_class": "Verb (unregelmäßig)",
        "verb_present": "schreibt",
        "verb_past": "schrieb",
        "verb_perfect": "hat geschrieben",
        "example_sentence": "Ich schreibe jeden Tag in mein Tagebuch.",
    }
    # _format_lernkarte wird auch von _generate_flashcards verwendet
    item = _format_lernkarte(glossar_card)
    # Alle drei Verbformen müssen landen
    assert item["extras"]["verb_present"] == "schreibt"
    assert item["extras"]["verb_past"] == "schrieb"
    assert item["extras"]["verb_perfect"] == "hat geschrieben"
    # Und die anderen Felder
    assert item["extras"]["word_class"] == "Verb (unregelmäßig)"
    assert item["extras"]["example_sentence"] == "Ich schreibe jeden Tag in mein Tagebuch."


def test_glossar_leere_verbformen_erzeugen_keine_schluessel():
    """Im Glossar-Weg, wenn ein Nomen (kein Verb) kommt, dürfen die Verbfelder
    nicht in extras auftauchen, auch wenn das Modell sie leer mitliefert."""
    glossar_card = {
        "begriff": "Metapher",
        "definition": "Ein Vergleich, der direkt ohne 'wie' gemacht wird.",
        "word_class": "Nomen",
        "singular": "die Metapher",
        "plural": "die Metaphern",
        "verb_present": "",
        "verb_past": "",
        "verb_perfect": "",
    }
    item = _format_lernkarte(glossar_card)
    # Verbformen dürfen nicht in extras sein
    assert "verb_present" not in item["extras"]
    assert "verb_past" not in item["extras"]
    assert "verb_perfect" not in item["extras"]
    # Andere Felder kommen durch
    assert item["extras"]["singular"] == "die Metapher"
    assert item["extras"]["plural"] == "die Metaphern"
