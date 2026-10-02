"""Topic store: the seed and the shape the generators expect."""

import inspect

from src.features.ai_assistant.repository.exercises import create_exercise_set_placeholder
from src.features.ai_assistant.repository.grammar_topics import (
    SEED_TOPICS,
    catalog_entry,
)


def test_a_set_is_stored_with_its_topic_not_with_a_catalogue_id():
    """Checking the signature catches bugs no single test sees."""
    params = inspect.signature(create_exercise_set_placeholder).parameters
    assert "grammar_topic_id" in params
    assert "grammar_type" not in params
    assert "grammar_kinds" in params


def test_every_seed_topic_carries_a_name():
    assert SEED_TOPICS
    for entry in SEED_TOPICS:
        assert entry["name"].strip()


def test_seed_names_are_unique():
    names = [e["name"] for e in SEED_TOPICS]
    assert len(names) == len(set(names))


def test_catalog_entry_has_the_shape_the_generators_expect():
    """The same shape from the database so nothing changes for the generators."""
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
    # An elaboration without an example must not crash the generator.
    entry = catalog_entry({"id": 1, "name": "X"}, {"rule": "r", "examples": []})
    assert entry["example"] == {"before": "", "after": ""}


def test_the_first_example_is_the_one_the_learner_sees():
    """All pairs steer the model, the first one is shown."""
    pairs = [
        {"before": "a b c.", "after": "c b a."},
        {"before": "d e f.", "after": "f e d."},
    ]
    entry = catalog_entry({"id": 1, "name": "X"}, {"rule": "r", "examples": pairs})
    assert entry["example"] == pairs[0]
    assert entry["examples"] == pairs


def _store(monkeypatch, before):
    """Stubs the spec store of the repository, counts pool clearings."""
    from src.features.ai_assistant.repository import grammar_topics as repo
    cleared = []
    monkeypatch.setattr(repo, "get_topic_spec", lambda tid, lang: {"examples": before})
    monkeypatch.setattr(repo, "save_topic_spec",
                        lambda tid, lang, rule, ex: {"rule": rule, "examples": ex})
    monkeypatch.setattr(repo, "clear_pool_for_topic", lambda tid: cleared.append(tid))
    return repo, cleared


def test_changed_examples_clear_the_topic_pool(monkeypatch):
    """Stored exercises carry the old pattern."""
    repo, cleared = _store(monkeypatch, [{"before": "a", "after": "b"}])
    repo.update_topic_examples(5, "de", "r", [{"before": "a", "after": "c"}])
    assert cleared == [5]


def test_unchanged_examples_keep_the_pool(monkeypatch):
    repo, cleared = _store(monkeypatch, [{"before": "a", "after": "b"}])
    repo.update_topic_examples(5, "de", "r", [{"before": "a", "after": "b"}])
    assert cleared == []
