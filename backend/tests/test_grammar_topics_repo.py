"""Themen-Ablage der Grammatik-Übung: Grundstock und Katalog-Form.

Themen standen bisher im Code. Ein neues kostete einen Eintrag mit Regel,
Musterpaar je Sprache und beim Ankreuz-Format noch drei falschen Formen. Deutsche
Grammatik hat Dutzende Themen, das ist über den Code nicht zu leisten.

Hier nur die reinen Funktionen. Datenbankzugriffe haben in diesen Tests nichts zu
suchen, sie werden in den Routen-Tests ausgehängt.
"""

import inspect

from src.features.ai_assistant.repository.exercises import create_exercise_set_placeholder
from src.features.ai_assistant.repository.grammar_topics import (
    SEED_TOPICS,
    catalog_entry,
)


def test_a_set_is_stored_with_its_topic_not_with_a_catalogue_id():
    """Am laufenden System aufgefallen: die Route reichte grammar_topic_id durch,
    die Ablage nahm aber weiter grammar_type, und das Anlegen brach mit einem 500 ab.

    Die Signatur zu prüfen kostet nichts und faengt genau diese Sorte Fehler, die
    kein Einzeltest sieht, weil beide Seiten fuer sich richtig aussehen.
    """
    params = inspect.signature(create_exercise_set_placeholder).parameters
    assert "grammar_topic_id" in params
    assert "grammar_type" not in params


def test_every_seed_topic_carries_a_name():
    assert SEED_TOPICS
    for entry in SEED_TOPICS:
        assert entry["name"].strip()


def test_seed_names_are_unique():
    names = [e["name"] for e in SEED_TOPICS]
    assert len(names) == len(set(names))


def test_catalog_entry_has_the_shape_the_generators_expect():
    """Die Generatoren bekamen bisher ein dict aus dem Code-Katalog. Bekommen sie
    genau dieselbe Form aus der Datenbank, ändert sich an ihnen keine Zeile."""
    topic = {"id": 3, "name": "Konjunktiv II"}
    spec = {
        "rule": "Input: indicative. Output: Konjunktiv II.",
        "examples": [{"before": "Er kommt morgen.", "after": "Er käme morgen."}],
    }
    entry = catalog_entry(topic, spec)
    assert entry["id"] == 3
    assert entry["label"] == "Konjunktiv II"
    assert entry["rule"] == spec["rule"]
    assert entry["example"] == spec["examples"][0]
    assert entry["examples"] == spec["examples"]


def test_catalog_entry_without_examples_stays_usable():
    # Eine Ausarbeitung ohne Beispiel darf den Generator nicht zum Absturz bringen.
    entry = catalog_entry({"id": 1, "name": "X"}, {"rule": "r", "examples": []})
    assert entry["example"] == {"before": "", "after": ""}


def test_the_first_example_is_the_one_the_learner_sees():
    """Der Dozent darf bis zu drei Paare hinterlegen. Alle steuern das Modell,
    aber die Aufgabe zeigt genau eines, und das ist das erste."""
    pairs = [
        {"before": "a b c.", "after": "c b a."},
        {"before": "d e f.", "after": "f e d."},
    ]
    entry = catalog_entry({"id": 1, "name": "X"}, {"rule": "r", "examples": pairs})
    assert entry["example"] == pairs[0]
    assert entry["examples"] == pairs
