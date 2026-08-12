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


# --- das Gedaechtnis ----------------------------------------------------------

def test_the_memory_comes_back_normalised(monkeypatch):
    monkeypatch.setattr("src.database.glossary_terms_used",
                        lambda *_a, **_k: ["Abstract", "Peer Review"])
    assert _glossary._terms_used(7, 1, "flashcards") == {"abstract", "peer review"}


def test_an_unreadable_memory_treats_every_term_as_fresh(monkeypatch):
    """Den Filter zu verlieren kostet eine wiederholte Karte, den Auftrag scheitern zu
    lassen kostet den ganzen Satz."""
    def boom(*_a, **_k):
        raise RuntimeError("database is having a day")

    monkeypatch.setattr("src.database.glossary_terms_used", boom)
    assert _glossary._terms_used(7, 1, "flashcards") == set()


# --- die Auswahl --------------------------------------------------------------

def _begriffe(gewaehlt):
    return [e["term_de"] for e in gewaehlt]


def test_fresh_terms_come_first():
    glossar = _eintraege(*[f"B{i}" for i in range(10)])
    gehabt = {"b0", "b1", "b2", "b3"}
    gewaehlt = _glossary._pick_terms(glossar, gehabt, 6)

    assert len(gewaehlt) == 6
    assert not ({b.lower() for b in _begriffe(gewaehlt)} & gehabt)


def test_the_shortfall_is_filled_from_the_used_ones():
    # Wer 6 anklickt, bekommt 6. Vier davon hatte die Person schon, das ist die
    # ehrlichere Antwort als ein Satz mit zwei Karten.
    glossar = _eintraege(*[f"B{i}" for i in range(10)])
    gehabt = {f"b{i}" for i in range(8)}
    begriffe = _begriffe(_glossary._pick_terms(glossar, gehabt, 6))

    assert len(begriffe) == 6
    assert len(set(begriffe)) == 6, "kein Begriff zweimal im selben Satz"
    assert len([b for b in begriffe if b.lower() not in gehabt]) == 2


def test_all_terms_used_still_fills_the_set():
    glossar = _eintraege(*[f"B{i}" for i in range(10)])
    gehabt = {f"b{i}" for i in range(10)}
    begriffe = _begriffe(_glossary._pick_terms(glossar, gehabt, 6))

    assert len(set(begriffe)) == 6


@pytest.mark.parametrize("gehabt", [set(), {"a", "b", "c"}])
def test_a_small_glossary_stays_short(gehabt):
    # Drei Begriffe geben drei Karten her und nicht zehn, so wie bisher auch.
    glossar = _eintraege("A", "B", "C")
    assert len(_glossary._pick_terms(glossar, gehabt, 10)) == 3


def test_the_same_term_from_two_sources_counts_once():
    # Die Eindeutigkeit in der Datenbank sitzt je Quelle, ein Kursraum hat aber mehrere
    # Quellen. "Abstract" aus einem Skript und "abstract" aus einer Vorlesung sind zwei
    # eigene Zeilen mit derselben Vergleichsform, das darf trotzdem nur eine Karte
    # ergeben. Beide Zeilen landen sonst in "frisch", und ein count von 2 zieht bei einem
    # Pool von genau 2 Elementen deterministisch beide, egal in welcher Reihenfolge
    # random.sample mischt. Der Test rutscht also nicht gelegentlich durch.
    glossar = _eintraege("Abstract", "abstract")
    gewaehlt = _glossary._pick_terms(glossar, set(), 2)

    assert len(gewaehlt) == 1
    assert gewaehlt[0]["term_de"] == "Abstract", "die erste Zeile gewinnt"


# --- der ganze Weg ------------------------------------------------------------

def test_the_set_avoids_the_terms_this_person_already_had(monkeypatch):
    glossar = _eintraege(*[f"B{i}" for i in range(10)])
    monkeypatch.setattr("src.database.get_aia_glossary_by_workspace",
                        lambda *_a, **_k: glossar)
    monkeypatch.setattr("src.database.glossary_terms_used",
                        lambda *_a, **_k: [f"B{i}" for i in range(6)])
    monkeypatch.setattr(_glossary, "title_from_glossary_terms", lambda *_a, **_k: "Titel")

    items, titel = _glossary.generate_from_glossary(
        _client(json.dumps({"cards": []})), "m", 7, 1, "flashcards", 4)

    assert titel == "Titel"
    assert {i["glossary_term"] for i in items} == {"B6", "B7", "B8", "B9"}


def test_an_empty_glossary_still_returns_none(monkeypatch):
    monkeypatch.setattr("src.database.get_aia_glossary_by_workspace", lambda *_a, **_k: [])
    assert _glossary.generate_from_glossary(
        _client("{}"), "m", 7, 1, "flashcards", 4) is None
