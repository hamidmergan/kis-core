"""The context sentence of a glossary entry is a quote or it is nothing."""

from src.features.ai_assistant.routes._text import _verbatim_or_empty


_KONTEXT = (
    "… Der deutsche Arbeitsmarkt   verlangt\nformale Abschlüsse. "
    "Viele Studierende unterschätzen das. …"
)


def test_a_sentence_from_the_page_survives_line_breaks_and_double_spaces():
    got = _verbatim_or_empty(
        "Der deutsche Arbeitsmarkt verlangt formale Abschlüsse.", _KONTEXT
    )
    assert got == "Der deutsche Arbeitsmarkt verlangt formale Abschlüsse."


def test_quotation_marks_around_the_sentence_are_stripped():
    got = _verbatim_or_empty(
        "„Viele Studierende unterschätzen das.“", _KONTEXT
    )
    assert got == "Viele Studierende unterschätzen das."


def test_an_invented_sentence_is_dropped():
    assert _verbatim_or_empty("Der Arbeitsmarkt ist hart.", _KONTEXT) == ""


def test_a_rephrased_sentence_is_dropped():
    got = _verbatim_or_empty(
        "Der deutsche Arbeitsmarkt verlangt Abschlüsse.", _KONTEXT
    )
    assert got == ""


def test_without_a_page_excerpt_nothing_is_kept():
    assert _verbatim_or_empty("Irgendein Satz.", "") == ""
