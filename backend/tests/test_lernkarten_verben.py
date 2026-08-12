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
