"""The glossary path remembers which terms a person already had."""

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
    """Stub that returns exactly one answer."""
    def create(**_kwargs):
        msg = types.SimpleNamespace(content=content)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)])

    return types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create)))


# --- the term stays on the card -----------------------------------------------

def test_the_plain_flashcard_carries_its_term():
    karte = _glossary._plain_flashcard(_eintraege("Abstract")[0])
    assert karte["glossary_term"] == "Abstract"


def test_the_fallback_karteikarte_carries_its_term():
    karte = _glossary._fallback_karteikarte(_eintraege("Abstract")[0], "German")
    assert karte["glossary_term"] == "Abstract"


def test_a_generated_karteikarte_carries_the_glossary_term_not_the_models():
    # The memory hangs off the glossary, not off the model's spelling.
    antwort = json.dumps({"cards": [
        {"term": "abstract", "question": "Was ist ein Abstract?",
         "answer": "Eine Zusammenfassung."},
    ]})
    items, _titel = _glossary._generate_karteikarten(
        _client(antwort), "m", _eintraege("Abstract"), "German")
    assert items[0]["glossary_term"] == "Abstract"


def test_a_generated_flashcard_carries_its_term():
    antwort = json.dumps({"cards": [
        {"begriff": "Abstract", "definition": "Eine kurze Zusammenfassung."},
    ]})
    items, _titel = _glossary._generate_flashcards(
        _client(antwort), "m", _eintraege("Abstract"), "German")
    assert items[0]["glossary_term"] == "Abstract"


# --- the memory ---------------------------------------------------------------

def test_the_memory_comes_back_normalised(monkeypatch):
    monkeypatch.setattr("src.database.glossary_terms_used",
                        lambda *_a, **_k: ["Abstract", "Peer Review"])
    assert _glossary._terms_used(7, 1, "flashcards") == {"abstract", "peer review"}


def test_an_unreadable_memory_treats_every_term_as_fresh(monkeypatch):
    """Losing the filter costs a card, losing the job costs the whole set."""
    def boom(*_a, **_k):
        raise RuntimeError("database is having a day")

    monkeypatch.setattr("src.database.glossary_terms_used", boom)
    assert _glossary._terms_used(7, 1, "flashcards") == set()


# --- the selection ------------------------------------------------------------

def _begriffe(gewaehlt):
    return [e["term_de"] for e in gewaehlt]


def test_fresh_terms_come_first():
    glossar = _eintraege(*[f"B{i}" for i in range(10)])
    gehabt = {"b0", "b1", "b2", "b3"}
    gewaehlt = _glossary._pick_terms(glossar, gehabt, 6)

    assert len(gewaehlt) == 6
    assert not ({b.lower() for b in _begriffe(gewaehlt)} & gehabt)


def test_the_shortfall_is_filled_from_the_used_ones():
    # Whoever clicks six gets six, repetitions included.
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
    # Three terms yield three cards and not ten, as before.
    glossar = _eintraege("A", "B", "C")
    assert len(_glossary._pick_terms(glossar, gehabt, 10)) == 3


def test_the_same_term_from_two_sources_counts_once():
    # Two rows with the same comparison form may yield only one card.
    glossar = _eintraege("Abstract", "abstract")
    gewaehlt = _glossary._pick_terms(glossar, set(), 2)

    assert len(gewaehlt) == 1
    assert gewaehlt[0]["term_de"] == "Abstract", "die erste Zeile gewinnt"


# --- the whole path -----------------------------------------------------------

def test_the_set_avoids_the_terms_this_person_already_had(monkeypatch):
    glossar = _eintraege(*[f"B{i}" for i in range(10)])
    monkeypatch.setattr("src.database.get_aia_glossary_by_workspace",
                        lambda *_a, **_k: glossar)
    monkeypatch.setattr("src.database.glossary_terms_used",
                        lambda *_a, **_k: [f"B{i}" for i in range(6)])
    items, titel = _glossary.generate_from_glossary(
        _client(json.dumps({"title": "Titel", "cards": []})), "m", 7, 1, "flashcards", 4)

    # The name rides along in the same answer, the set costs no title call.
    assert titel == "Titel"
    assert {i["glossary_term"] for i in items} == {"B6", "B7", "B8", "B9"}


def test_without_a_title_in_the_answer_the_terms_name_the_set(monkeypatch):
    glossar = _eintraege("Abstract", "Peer Review")
    monkeypatch.setattr("src.database.get_aia_glossary_by_workspace",
                        lambda *_a, **_k: glossar)
    monkeypatch.setattr("src.database.glossary_terms_used", lambda *_a, **_k: [])

    _items, titel = _glossary.generate_from_glossary(
        _client("kein JSON"), "m", 7, 1, "flashcards", 2)

    assert sorted(titel.split(", ")) == ["Abstract", "Peer Review"]


def test_an_empty_glossary_still_returns_none(monkeypatch):
    monkeypatch.setattr("src.database.get_aia_glossary_by_workspace", lambda *_a, **_k: [])
    assert _glossary.generate_from_glossary(
        _client("{}"), "m", 7, 1, "flashcards", 4) is None


# --- wiring in the job --------------------------------------------------------

@pytest.fixture
def glossar_stack(monkeypatch):
    """Hooks the job up to stubs and records what gets saved."""
    import src.features.ai_assistant.tasks.language_training as mod

    seen = {"items": None, "failed": False}

    class _DB:
        def get_aia_workspace_by_id(self, _id):
            return {"id": 7}

        def get_exercise_set_with_items(self, _id):
            return {"user_id": 1}

        def finalize_exercise_set(self, _set_id, _title, items, header=None, user_id=None):
            seen["items"] = items

        def fail_exercise_set(self, _id):
            seen["failed"] = True

    monkeypatch.setattr(mod, "db", _DB())
    monkeypatch.setattr(mod, "_get_llm_client", lambda: (object(), "m", "p"))
    monkeypatch.setattr(mod, "build_adaptive_tool_suffix", lambda *a, **k: "")
    monkeypatch.setattr(mod, "build_title_avoidance_block", lambda *a, **k: "")
    monkeypatch.setattr(mod, "resolve_set_title", lambda *a, **k: "Titel")
    return mod, seen


def test_a_deliberately_repeated_term_reaches_the_set(glossar_stack, monkeypatch):
    """The second pass must not stay stuck on the old filter."""
    mod, seen = glossar_stack
    monkeypatch.setattr(mod, "generate_from_glossary", lambda *a, **k: (
        [{"front": "Abstract", "back": "Eine Zusammenfassung.",
          "glossary_term": "Abstract"}], "T"))
    monkeypatch.setattr(mod, "seen_by_user", lambda *a, **k: ["Abstract"])

    mod.run_generate_exercise_set(1, 7, "flashcards", "glossary", 1)

    assert seen["failed"] is False
    assert [i["front"] for i in seen["items"]] == ["Abstract"]


def test_two_identical_cards_in_one_set_still_collapse(glossar_stack, monkeypatch):
    """Two identical cards side by side stay a visible bug."""
    mod, seen = glossar_stack
    monkeypatch.setattr(mod, "generate_from_glossary", lambda *a, **k: (
        [{"front": "Was ist ein Abstract?", "back": "A", "glossary_term": "Abstract"},
         {"front": "Was ist ein Abstract?", "back": "B", "glossary_term": "Exposé"}], "T"))
    monkeypatch.setattr(mod, "seen_by_user", lambda *a, **k: [])

    mod.run_generate_exercise_set(1, 7, "karteikarten", "glossary", 2)

    assert len(seen["items"]) == 1
