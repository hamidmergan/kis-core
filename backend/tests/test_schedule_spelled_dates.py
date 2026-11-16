"""Dates written out in words, so the model is not needed to find them."""

import pytest

from src.features.ai_assistant.tasks.studio.schedule._regex import _date_candidates_in_text


def _first(text: str):
    found = _date_candidates_in_text(text)
    assert found, f"nichts gefunden in {text!r}"
    return found[0]


@pytest.mark.parametrize("text, raw", [
    ("Die Klausur ist am dritten Februar 2026 um 10 Uhr.", "dritten Februar 2026"),
    ("Abgabe bis zum einunddreißigsten Dezember 2026.", "einunddreißigsten Dezember 2026"),
    ("Treffen am zwanzigsten Mai 2027.", "zwanzigsten Mai 2027"),
    ("The exam is on the third of February 2026.", "the third of February 2026"),
    ("Submission by the twenty-first of March 2026.", "the twenty-first of March 2026"),
])
def test_a_written_out_date_with_year_is_found(text, raw):
    s, e, got, has_year, prec = _first(text)
    assert (got, has_year, prec) == (raw, True, "day")


@pytest.mark.parametrize("text, raw", [
    ("Die Klausur ist am dritten Februar.", "dritten Februar"),
    ("We meet on the third of February.", "the third of February"),
])
def test_a_written_out_date_without_year_is_found(text, raw):
    s, e, got, has_year, prec = _first(text)
    assert (got, has_year, prec) == (raw, False, "day")


@pytest.mark.parametrize("text", [
    "Erste Hilfe ist wichtig.",
    "Das dritte Kapitel behandelt die Grundlagen.",
    "First things first.",
])
def test_an_ordinal_without_a_month_is_no_date(text):
    assert _date_candidates_in_text(text) == []


def test_the_digit_form_still_works():
    s, e, raw, has_year, prec = _first("Die Klausur ist am 14.03.2026.")
    assert (raw, has_year, prec) == ("14.03.2026", True, "day")


@pytest.mark.parametrize("text, raw", [
    ("The deadline is January 15, 2026.", "January 15, 2026"),
    ("The exam is February 3, 2026.", "February 3, 2026"),
    ("Submission March 21, 2026.", "March 21, 2026"),
])
def test_english_month_names_are_found(text, raw):
    s, e, got, has_year, prec = _first(text)
    assert (got, has_year, prec) == (raw, True, "day")
