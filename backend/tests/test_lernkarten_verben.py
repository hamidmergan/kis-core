"""Verb details on the flashcard, from the model into the extras."""

import json
import types

from src.features.ai_assistant.tasks.language_training._glossary import _generate_flashcards
from src.features.ai_assistant.tasks.language_training._source_flashcards import (
    _format_lernkarte,
    AIA_FLASHCARD_EXTRAS_FIELDS,
)
from src.features.ai_assistant.prompts.language_training_prompts import AIA_LERNKARTEN_PROMPT


def _fake_client(content: str):
    """Model stub: always returns the same answer, no network, no database."""
    def create(model, messages, **kwargs):
        message = types.SimpleNamespace(content=content)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])

    return types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create))
    )


# --- the path into extras ----------------------------------------------------

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
    """A noun must not create the verb fields in the first place."""
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
    """Old sets and models that do not know the fields stay unchanged."""
    item = _format_lernkarte({"begriff": "X", "definition": "Y"})
    assert item.get("extras") is None


# --- the rules in the prompt -------------------------------------------------

def test_prompt_kennt_die_drei_felder():
    for feld in ("verb_present", "verb_past", "verb_perfect"):
        assert feld in AIA_LERNKARTEN_PROMPT


def test_prompt_verlangt_das_hilfsverb_im_perfekt():
    """Without the auxiliary the perfect form is worthless to the learner."""
    assert "hat sich getroffen" in AIA_LERNKARTEN_PROMPT
    assert "MUST carry its auxiliary" in AIA_LERNKARTEN_PROMPT


def test_prompt_verbietet_zu_raten():
    """Better a missing line than an invented form on a flashcard."""
    assert "leave ALL THREE empty" in AIA_LERNKARTEN_PROMPT


def test_prompt_haelt_die_formen_in_der_quellsprache():
    """The forms are the learning material, they are never translated into the explanation language."""
    assert (
        "the verb forms in 'verb_present', 'verb_past' and 'verb_perfect'"
        in AIA_LERNKARTEN_PROMPT
    )


def test_prompt_kennt_die_klammer_hinter_der_wortart():
    assert "Verb (unregelmäßig, reflexiv)" in AIA_LERNKARTEN_PROMPT


# --- shared constant for source text and glossary ----------------------------

def test_gemeinsame_konstante_enthaelt_alle_felder():
    """The shared field list applies to both paths and has to contain everything."""
    assert "verb_present" in AIA_FLASHCARD_EXTRAS_FIELDS
    assert "verb_past" in AIA_FLASHCARD_EXTRAS_FIELDS
    assert "verb_perfect" in AIA_FLASHCARD_EXTRAS_FIELDS
    # And the established fields
    assert "word_parts" in AIA_FLASHCARD_EXTRAS_FIELDS
    assert "word_class" in AIA_FLASHCARD_EXTRAS_FIELDS
    assert "singular" in AIA_FLASHCARD_EXTRAS_FIELDS
    assert "plural" in AIA_FLASHCARD_EXTRAS_FIELDS


def test_glossar_verbformen_landen_in_extras():
    """The glossary path puts verb forms into extras correctly."""
    # Model answer with a verb in all three tenses
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

    items, _titel = _generate_flashcards(client, "modell", glossary_entries, "German")

    # All three verb forms have to land in extras
    assert items[0]["extras"]["verb_present"] == "schreibt"
    assert items[0]["extras"]["verb_past"] == "schrieb"
    assert items[0]["extras"]["verb_perfect"] == "hat geschrieben"
    # The other fields too
    assert items[0]["extras"]["word_class"] == "Verb (unregelmäßig)"
    assert items[0]["extras"]["example_sentence"] == "Ich schreibe."


def test_glossar_leere_verbformen_erzeugen_keine_schluessel():
    """Empty verb forms do not land in extras on the glossary path either."""
    # Model answer with a noun (no verb forms)
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

    items, _titel = _generate_flashcards(client, "modell", glossary_entries, "German")

    # Empty verb forms must not be in extras
    extras = items[0].get("extras", {})
    assert "verb_present" not in extras
    assert "verb_past" not in extras
    assert "verb_perfect" not in extras
    # But the established fields come through
    assert extras["singular"] == "die Metapher"
    assert extras["plural"] == "die Metaphern"
    assert extras["word_class"] == "Nomen"


# --- fixed preposition of a verb ---------------------------------------------

def test_feste_praeposition_landet_in_extras():
    item = _format_lernkarte({
        "begriff": "sich beklagen",
        "definition": "Sagen, dass man unzufrieden ist.",
        "word_class": "Verb (regelmäßig, reflexiv)",
        "verb_preposition": " über + Akk. ",
    })
    assert item["extras"]["verb_preposition"] == "über + Akk."


def test_verb_ohne_praeposition_bekommt_keinen_schluessel():
    item = _format_lernkarte({
        "begriff": "lernen", "definition": "D", "verb_present": "lernt", "verb_preposition": "",
    })
    assert "verb_preposition" not in item["extras"]


def test_prompt_verlangt_praeposition_mit_kasus():
    """The case is what the learner cannot guess, so the examples carry it."""
    assert "verb_preposition" in AIA_LERNKARTEN_PROMPT
    assert "'sich beklagen' -> 'über + Akk.'" in AIA_LERNKARTEN_PROMPT
    assert "'gratulieren' -> 'zu + Dat.'" in AIA_LERNKARTEN_PROMPT


def test_prompt_haelt_die_praeposition_in_der_quellsprache():
    assert "the preposition in 'verb_preposition' stay in that same language" in AIA_LERNKARTEN_PROMPT


def test_gemeinsame_konstante_kennt_die_praeposition():
    assert "verb_preposition" in AIA_FLASHCARD_EXTRAS_FIELDS


# --- separable and irregular, read off the forms -----------------------------

def test_prompt_kennt_trennbar_in_der_klammer():
    assert "'unterheben' -> 'Verb (unregelmäßig, trennbar)'" in AIA_LERNKARTEN_PROMPT
    assert "'unterrichten' -> 'Verb (regelmäßig, untrennbar)'" in AIA_LERNKARTEN_PROMPT


def test_prompt_trennt_die_formen_trennbarer_verben():
    """'unterhob' was on a card although only 'hob unter' is correct."""
    assert "verb_past='hob unter'" in AIA_LERNKARTEN_PROMPT


def test_wortart_steht_hinter_den_verbformen():
    """The bracket is read off the forms, so the model has to write the forms first."""
    schema = AIA_LERNKARTEN_PROMPT.split("Rules:")[0]
    assert schema.index('"verb_perfect"') < schema.index('"word_class"')
    assert "Decide the bracket FROM the verb forms" in AIA_LERNKARTEN_PROMPT
