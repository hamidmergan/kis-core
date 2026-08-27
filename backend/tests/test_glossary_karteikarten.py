"""Flashcards from the glossary carry a question, not a bare term."""

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
    """Stub that returns exactly one answer and records the calls."""
    calls = []

    def create(**kwargs):
        calls.append(kwargs)
        msg = types.SimpleNamespace(content=content)
        return types.SimpleNamespace(choices=[types.SimpleNamespace(message=msg)])

    client = types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create)))
    return client, calls


def test_the_front_is_a_question_not_the_term():
    antwort = json.dumps({"cards": [
        {"term": "Literaturrecherche", "question": "Wozu dient die Literaturrecherche?",
         "answer": "Sie findet Quellen zum eigenen Thema."},
    ]})
    client, _ = _client(antwort)
    items = _glossary._generate_karteikarten(
        client, "m", _eintraege("Literaturrecherche"), "German")

    assert items[0]["front"] == "Wozu dient die Literaturrecherche?"
    assert items[0]["front"] != "Literaturrecherche"
    assert items[0]["back"] == "Sie findet Quellen zum eigenen Thema."


def test_one_call_for_the_whole_set():
    # One batched call, not one per term.
    antwort = json.dumps({"cards": [
        {"term": b, "question": f"Was ist {b}?", "answer": f"Das ist {b}."}
        for b in ("Abstract", "Peer Review", "Exposé")
    ]})
    client, calls = _client(antwort)
    items = _glossary._generate_karteikarten(
        client, "m", _eintraege("Abstract", "Peer Review", "Exposé"), "German")

    assert len(calls) == 1
    assert len(items) == 3


def test_the_source_page_stays_with_the_card():
    # Page and file come from the glossary and the model must not overwrite them.
    antwort = json.dumps({"cards": [
        {"term": "Abstract", "question": "Was ist ein Abstract?", "answer": "Eine Zusammenfassung."},
    ]})
    client, _ = _client(antwort)
    items = _glossary._generate_karteikarten(client, "m", _eintraege("Abstract"), "German")

    assert items[0]["page_number"] == 3
    assert items[0]["source_label"] == "Skript.pdf"
    assert items[0]["sources"][0]["page_number"] == 3


def test_a_failing_call_still_yields_questions():
    def boom(**_kwargs):
        raise RuntimeError("Connection error.")

    client = types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=boom)))
    items = _glossary._generate_karteikarten(client, "m", _eintraege("Abstract"), "German")

    assert items[0]["front"] == "Was bedeutet „Abstract\"?"
    assert items[0]["back"] == "Das ist Abstract."


def test_a_term_the_model_skipped_falls_back():
    antwort = json.dumps({"cards": [
        {"term": "Abstract", "question": "Was ist ein Abstract?", "answer": "Eine Zusammenfassung."},
    ]})
    client, _ = _client(antwort)
    items = _glossary._generate_karteikarten(
        client, "m", _eintraege("Abstract", "Exposé"), "German")

    assert len(items) == 2
    assert items[1]["front"] == "Was bedeutet „Exposé\"?"


def test_an_empty_question_counts_as_missing():
    # An empty field would be exactly the state this path is meant to fix.
    antwort = json.dumps({"cards": [
        {"term": "Abstract", "question": "   ", "answer": "Eine Zusammenfassung."},
    ]})
    client, _ = _client(antwort)
    items = _glossary._generate_karteikarten(client, "m", _eintraege("Abstract"), "German")
    assert items[0]["front"] == "Was bedeutet „Abstract\"?"


def test_broken_json_falls_back_instead_of_failing():
    client, _ = _client("kein JSON weit und breit")
    items = _glossary._generate_karteikarten(client, "m", _eintraege("Abstract"), "German")
    assert items[0]["front"] == "Was bedeutet „Abstract\"?"


@pytest.mark.parametrize("gegeben,erwartet", [
    ("German", 'Was bedeutet „Abstract"?'),
    ("English", 'What does "Abstract" mean?'),
])
def test_the_fallback_follows_the_generation_language(gegeben, erwartet):
    items = [_glossary._fallback_karteikarte(e, gegeben) for e in _eintraege("Abstract")]
    assert items[0]["front"] == erwartet
