"""What the route makes of a submitted format selection, mixed becomes NULL."""

from src.services.aia_grammar_formats import clean_kinds


def test_nothing_sent_means_mixed():
    assert clean_kinds(None) is None


def test_an_empty_list_means_mixed():
    assert clean_kinds([]) is None


def test_all_four_mean_mixed():
    """Ticking all four is mixed, two spellings drifted apart."""
    assert clean_kinds(["transform", "cloze", "statement", "choice"]) is None


def test_a_real_choice_survives():
    assert clean_kinds(["transform", "cloze"]) == ["transform", "cloze"]


def test_the_order_is_the_catalogue_order_not_the_sent_one():
    """Otherwise the distribution would hang off the click order."""
    assert clean_kinds(["choice", "transform"]) == ["transform", "choice"]


def test_duplicates_are_folded():
    assert clean_kinds(["cloze", "cloze"]) == ["cloze"]


def test_unknown_kinds_are_dropped():
    assert clean_kinds(["transform", "malen"]) == ["transform"]


def test_only_unknown_kinds_mean_mixed():
    """Nothing usable submitted yields mixed, not an error."""
    assert clean_kinds(["malen", "singen"]) is None


def test_junk_types_do_not_crash():
    assert clean_kinds(["transform", None, 5, {"a": 1}]) == ["transform"]


def test_something_that_is_not_a_list_means_mixed():
    assert clean_kinds("transform") is None


def test_the_catalogue_is_the_same_one_the_generator_uses():
    """Two catalogues would let a kind through that the generator does not know."""
    from src.features.ai_assistant.tasks.language_training import _source_grammar
    from src.services.aia_grammar_formats import KINDS

    assert _source_grammar.KINDS is KINDS
