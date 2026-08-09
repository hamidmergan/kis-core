"""Exercises the workspace already has are dropped before the set is saved.

The comparison is exact on the normalised front, and the tests below pin down why: the
near-misses that a fuzzy comparison would also catch are, in the measured data, separate
exercises that share an instruction line.
"""

import pytest

from src.features.ai_assistant.tasks.language_training._dedup import (
    drop_repeats,
    item_key,
    seen_by_user,
)


def _items(*fronts: str) -> list[dict]:
    return [{"front": f, "back": "irgendeine Antwort"} for f in fronts]


def test_drops_what_the_workspace_already_has():
    kept, dropped = drop_repeats(_items("Literaturrecherche", "Peer Review"),
                                 ["Literaturrecherche"])
    assert [i["front"] for i in kept] == ["Peer Review"]
    assert dropped == 1


def test_drops_repeats_inside_one_set_too():
    # Two generation runs get merged for a top-up, and each only knows its own items.
    kept, dropped = drop_repeats(_items("Abstract", "Peer Review", "Abstract"), [])
    assert [i["front"] for i in kept] == ["Abstract", "Peer Review"]
    assert dropped == 1


def test_first_occurrence_wins_and_order_survives():
    kept, _ = drop_repeats(_items("A", "B", "A", "C"), [])
    assert [i["front"] for i in kept] == ["A", "B", "C"]


def test_case_quotes_and_punctuation_do_not_make_a_new_exercise():
    # Measured in the database: the same sentence came back once with single and once
    # with double quotes, and a term came back capitalised differently.
    kept, dropped = drop_repeats(
        _items('Im Vorgangspassiv wird das Hilfsverb "sein" verwendet.'),
        ["Im Vorgangspassiv wird das Hilfsverb 'sein' verwendet."],
    )
    assert kept == []
    assert dropped == 1
    kept, _ = drop_repeats(_items("wissenschaftliches Seminar"), ["Wissenschaftliches Seminar"])
    assert kept == []


def test_two_exercises_sharing_an_instruction_line_are_not_repeats():
    """The reason the comparison is exact and not fuzzy.

    These two score 0.949 on character similarity because they share the instruction and
    the sentence frame, but they are different exercises with different answers. A fuzzy
    threshold low enough to catch real repeats also swallows these.
    """
    a = "**Setze den Satz ins Passiv Präsens.**\n\nDie Studierenden stellen die Forschungsfrage."
    b = "**Setze den Satz ins Passiv Präsens.**\n\nDie Studierenden schreiben die Forschungsfrage."
    kept, dropped = drop_repeats(_items(b), [a])
    assert [i["front"] for i in kept] == [b]
    assert dropped == 0


def test_an_item_without_a_usable_front_is_kept():
    # Rejecting those is the generators' job; dropping them here would hide the problem
    # inside a duplicate count.
    kept, dropped = drop_repeats([{"front": "", "back": "x"}, {"front": "   ", "back": "y"}], [])
    assert len(kept) == 2
    assert dropped == 0


def test_empty_inputs():
    assert drop_repeats([], ["A"]) == ([], 0)
    kept, dropped = drop_repeats(_items("A"), [])
    assert len(kept) == 1 and dropped == 0


def test_item_key_is_language_agnostic():
    # No word list anywhere: normalisation goes by Unicode category, so the same folding
    # applies to a language the tool has never seen.
    assert item_key("Le Résumé!") == item_key("le résumé")
    assert item_key("Ταξινόμηση;") == item_key("ταξινόμηση")


def test_seen_by_user_without_a_user_is_empty():
    assert seen_by_user(None, "flashcards") == []


def test_seen_by_user_survives_a_failing_read(monkeypatch):
    # Losing the filter costs a repeated exercise, raising here would cost the whole set.
    def boom(*_args, **_kwargs):
        raise RuntimeError("database is having a day")

    monkeypatch.setattr("src.database.seen_fingerprints", boom)
    assert seen_by_user(7, "quiz") == []


def test_seen_by_user_reads_the_user_and_tool(monkeypatch):
    """Nach Person, nicht nach Kursraum.

    Seit es den Vorrat gibt, ist eine Aufgabe, die jemand anderes erzeugt hat, fuer
    diese Person neu und soll ihr angeboten werden. Nur was sie selbst schon hatte, ist
    eine Wiederholung.
    """
    gesehen = {}

    def fake(user_id, tool):
        gesehen["args"] = (user_id, tool)
        return ["Abstract"]

    monkeypatch.setattr("src.database.seen_fingerprints", fake)
    assert seen_by_user(7, "quiz") == ["Abstract"]
    assert gesehen["args"] == (7, "quiz")


@pytest.mark.parametrize("front", ["Abstract", "  Abstract  ", "abstract."])
def test_the_same_term_in_different_shapes_is_one_exercise(front):
    kept, _ = drop_repeats(_items(front), ["Abstract"])
    assert kept == []
