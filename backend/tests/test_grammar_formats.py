"""Was die Route aus einer gesendeten Formatauswahl macht.

Gemischt ist der Normalfall und wird als NULL gespeichert. Es gibt genau EINEN Weg,
gemischt auszudruecken, und das ist "nichts gewaehlt". Eine leere Liste und alle vier
Arten bedeuten dasselbe und werden deshalb beide zu None.

Kein DB- und kein Netzzugriff.
"""

from src.services.aia_grammar_formats import clean_kinds


def test_nothing_sent_means_mixed():
    assert clean_kinds(None) is None


def test_an_empty_list_means_mixed():
    assert clean_kinds([]) is None


def test_all_four_mean_mixed():
    """Alle vier anzuhaken IST gemischt. Zwei Schreibweisen fuer denselben Zustand
    waeren zwei Faelle, die auseinanderlaufen koennen."""
    assert clean_kinds(["transform", "cloze", "statement", "choice"]) is None


def test_a_real_choice_survives():
    assert clean_kinds(["transform", "cloze"]) == ["transform", "cloze"]


def test_the_order_is_the_catalogue_order_not_the_sent_one():
    """Sonst haengt die Verteilung im Plan daran, in welcher Reihenfolge jemand
    geklickt hat."""
    assert clean_kinds(["choice", "transform"]) == ["transform", "choice"]


def test_duplicates_are_folded():
    assert clean_kinds(["cloze", "cloze"]) == ["cloze"]


def test_unknown_kinds_are_dropped():
    assert clean_kinds(["transform", "malen"]) == ["transform"]


def test_only_unknown_kinds_mean_mixed():
    """Nichts Brauchbares gesendet. Ein Fehler waere haerter als noetig, denn
    gemischt ist eine gueltige Uebung."""
    assert clean_kinds(["malen", "singen"]) is None


def test_junk_types_do_not_crash():
    assert clean_kinds(["transform", None, 5, {"a": 1}]) == ["transform"]


def test_something_that_is_not_a_list_means_mixed():
    assert clean_kinds("transform") is None


def test_the_catalogue_is_the_same_one_the_generator_uses():
    """Zwei Kataloge, die auseinanderlaufen, wuerden hier eine Art durchlassen, die
    der Erzeuger nicht kennt."""
    from src.features.ai_assistant.tasks.language_training import _source_grammar
    from src.services.aia_grammar_formats import KINDS

    assert _source_grammar.KINDS is KINDS
