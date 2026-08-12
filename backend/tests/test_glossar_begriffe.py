"""Der Glossar-Weg merkt sich, welche Begriffe eine Person schon hatte.

Bis 2026-08-12 zog er blind aus der ganzen Liste und filterte erst hinterher ueber die
Vorderseite der fertigen Karte. Bei Lernkarten IST die Vorderseite der Begriff, dort
wurde der Satz nur kuerzer und der Modellaufruf war schon bezahlt. Bei Karteikarten ist
sie eine erzeugte Frage, die bei jedem Lauf anders lautet, und der Filter griff gar nicht.

Kein Datenbank- und kein Netzzugriff, beide sind ausgetauscht.
"""

import json
import types

import pytest

from src.features.ai_assistant.tasks.language_training import _glossary


def _eintraege(*begriffe):
    return [
        {"term_de": b, "term_en": f"{b}-en", "definition": f"Das ist {b}.",
         "filename": "Skript.pdf", "page_number": 3}
        for b in begriffe
    ]


def _client(content: str):
    """Attrappe, die genau eine Antwort liefert."""
    def create(**_kwargs):
        msg = types.SimpleNamespace(content=content)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)])

    return types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create)))


# --- der Begriff bleibt an der Karte ------------------------------------------

def test_the_plain_flashcard_carries_its_term():
    karte = _glossary._plain_flashcard(_eintraege("Abstract")[0])
    assert karte["glossary_term"] == "Abstract"


def test_the_fallback_karteikarte_carries_its_term():
    karte = _glossary._fallback_karteikarte(_eintraege("Abstract")[0], "German")
    assert karte["glossary_term"] == "Abstract"


def test_a_generated_karteikarte_carries_the_glossary_term_not_the_models():
    # Das Modell bekommt den Begriff und gibt ihn kleingeschrieben zurueck. Das
    # Gedaechtnis haengt am Glossar und nicht daran, was das Modell daraus macht.
    antwort = json.dumps({"cards": [
        {"term": "abstract", "question": "Was ist ein Abstract?",
         "answer": "Eine Zusammenfassung."},
    ]})
    items = _glossary._generate_karteikarten(
        _client(antwort), "m", _eintraege("Abstract"), "German")
    assert items[0]["glossary_term"] == "Abstract"


def test_a_generated_flashcard_carries_its_term():
    antwort = json.dumps({"cards": [
        {"begriff": "Abstract", "definition": "Eine kurze Zusammenfassung."},
    ]})
    items = _glossary._generate_flashcards(
        _client(antwort), "m", _eintraege("Abstract"), "German")
    assert items[0]["glossary_term"] == "Abstract"
