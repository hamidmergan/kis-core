"""Date forms the regex has to catch so no chunk with a date is missed."""

import pytest

from src.features.ai_assistant.tasks.studio.schedule._regex import _date_candidates_in_text
from src.features.ai_assistant.tasks.studio.schedule._parse import (
    _normalize_date, _normalize_month_date, _normalize_partial_date,
)


def _only(text: str):
    found = _date_candidates_in_text(text)
    assert len(found) == 1, f"erwartet genau einen Treffer in {text!r}, bekam {found}"
    return found[0]


@pytest.mark.parametrize("text, raw, iso", [
    ("Die Abgabe ist im Januar 2026 geplant.", "Januar 2026", "2026-01-01"),
    ("The retake takes place in July 2026.", "July 2026", "2026-07-01"),
    ("Start der Vorlesung: Sept 2026.", "Sept 2026", "2026-09-01"),
])
def test_month_name_with_year_is_a_month_hit(text, raw, iso):
    s, e, got, has_year, prec = _only(text)
    assert (got, has_year, prec) == (raw, True, "month")
    assert _normalize_month_date(got) == iso


@pytest.mark.parametrize("text, raw", [
    ("Die Klausur ist im Januar.", "Januar"),
    ("Submissions open in July.", "July"),
    ("Die Exkursion findet ab Oktober statt.", "Oktober"),
])
def test_month_name_after_a_preposition_without_year_is_a_yearless_month_hit(text, raw):
    s, e, got, has_year, prec = _only(text)
    assert (got, has_year, prec) == (raw, False, "month")


@pytest.mark.parametrize("text", [
    "Der Januar war kalt.",
    "Mai ist ein Vorname.",
])
def test_a_bare_month_word_without_preposition_is_no_hit(text):
    assert _date_candidates_in_text(text) == []


def test_month_with_year_beats_the_yearless_month_at_the_same_spot():
    s, e, got, has_year, prec = _only("Das Semester beginnt im Oktober 2026.")
    assert (got, has_year) == ("Oktober 2026", True)


def test_day_month_year_beats_the_month_with_year_inside_it():
    s, e, got, has_year, prec = _only("Abgabe am 3. Juli 2026 um 12 Uhr.")
    assert (got, prec) == ("3. Juli 2026", "day")


@pytest.mark.parametrize("text, raw, iso", [
    ("Abgabe bis 3.6.26 um 12 Uhr.", "3.6.26", "2026-06-03"),
    ("Klausur am 03.06.26.", "03.06.26", "2026-06-03"),
])
def test_two_digit_year_is_expanded_to_this_century(text, raw, iso):
    s, e, got, has_year, prec = _only(text)
    assert (got, has_year, prec) == (raw, True, "day")
    assert _normalize_date(got) == iso


def test_two_digit_year_does_not_eat_a_four_digit_one():
    s, e, got, has_year, prec = _only("Klausur am 03.06.2026.")
    assert got == "03.06.2026"


@pytest.mark.parametrize("text, raw, iso", [
    ("Deadline: 03/06/2026.", "03/06/2026", "2026-06-03"),
    ("Deadline: 3-6-2026.", "3-6-2026", "2026-06-03"),
])
def test_slash_and_dash_separators_are_day_month_year(text, raw, iso):
    s, e, got, has_year, prec = _only(text)
    assert (got, has_year, prec) == (raw, True, "day")
    assert _normalize_date(got) == iso


def test_iso_date_is_not_mistaken_for_a_dash_form():
    s, e, got, has_year, prec = _only("Deadline: 2026-07-03.")
    assert got == "2026-07-03"


@pytest.mark.parametrize("text, raw, iso", [
    ("The exam is on 3 July 2026.", "3 July 2026", "2026-07-03"),
    ("Submission by 3rd July 2026.", "3rd July 2026", "2026-07-03"),
    ("Submission by the 21st of March 2026.", "21st of March 2026", "2026-03-21"),
])
def test_english_day_before_month_with_year(text, raw, iso):
    s, e, got, has_year, prec = _only(text)
    assert (got, has_year, prec) == (raw, True, "day")
    assert _normalize_date(got) == iso


@pytest.mark.parametrize("text, raw, tag_monat", [
    ("The exam is on 3 July.", "3 July", (7, 3)),
    ("Submission by 3rd July.", "3rd July", (7, 3)),
])
def test_english_day_before_month_without_year(text, raw, tag_monat):
    s, e, got, has_year, prec = _only(text)
    assert (got, has_year, prec) == (raw, False, "day")
    assert _normalize_partial_date(got) == tag_monat


@pytest.mark.parametrize("text, raw", [
    ("Ende Mai, genau, da ist die freiwillige Abgabe.", "Mai"),
    ("Anfang Juli ist alles abzugeben.", "Juli"),
    ("Mitte Oktober startet die Vorlesung.", "Oktober"),
    ("The draft is due late May.", "May"),
    ("We start at the beginning of October.", "October"),
    ("Submit by the end of July.", "July"),
])
def test_a_month_after_a_part_of_month_word_is_a_yearless_month_hit(text, raw):
    s, e, got, has_year, prec = _only(text)
    assert (got, has_year, prec) == (raw, False, "month")
