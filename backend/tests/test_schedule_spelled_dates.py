"""Dates written out in words, so the model is not needed to find them."""

import pytest

from src.features.ai_assistant.tasks.studio.schedule._regex import _date_candidates_in_text
from src.features.ai_assistant.tasks.studio.schedule._parse import (
    _normalize_date, _normalize_partial_date,
)


def _first(text: str):
    found = _date_candidates_in_text(text)
    assert found, f"nichts gefunden in {text!r}"
    return found[0]


@pytest.mark.parametrize("text, iso", [
    ("Die Klausur ist am dritten Februar 2026 um 10 Uhr.", "2026-02-03"),
    ("Abgabe bis zum einunddreißigsten Dezember 2026.", "2026-12-31"),
    ("Treffen am zwanzigsten Mai 2027.", "2027-05-20"),
    ("The exam is on the third of February 2026.", "2026-02-03"),
    ("Submission by the twenty-first of March 2026.", "2026-03-21"),
])
def test_a_written_out_date_with_year_becomes_iso(text, iso):
    s, e, raw, has_year, prec = _first(text)
    assert has_year
    assert _normalize_date(raw) == iso


@pytest.mark.parametrize("text, tag_monat", [
    ("Die Klausur ist am dritten Februar.", (2, 3)),
    ("We meet on the third of February.", (2, 3)),
])
def test_a_written_out_date_without_year_keeps_day_and_month(text, tag_monat):
    s, e, raw, has_year, prec = _first(text)
    assert not has_year
    assert _normalize_partial_date(raw) == tag_monat


@pytest.mark.parametrize("text", [
    "Erste Hilfe ist wichtig.",
    "Das dritte Kapitel behandelt die Grundlagen.",
    "First things first.",
])
def test_an_ordinal_without_a_month_is_no_date(text):
    assert _date_candidates_in_text(text) == []


def test_the_digit_form_still_works():
    s, e, raw, has_year, prec = _first("Die Klausur ist am 14.03.2026.")
    assert _normalize_date(raw) == "2026-03-14"


@pytest.mark.parametrize("text, iso", [
    ("The deadline is January 15, 2026.", "2026-01-15"),
    ("The exam is February 3, 2026.", "2026-02-03"),
    ("Submission March 21, 2026.", "2026-03-21"),
])
def test_english_month_names_are_understood(text, iso):
    """January, February and March were found but never converted."""
    s, e, raw, has_year, prec = _first(text)
    assert _normalize_date(raw) == iso
