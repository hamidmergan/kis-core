"""Ziffern gehen als Wörter an die Vertonung, sonst spricht sie sie deutsch."""

import pytest

from src.services.tts_number_words import spell_numbers


@pytest.mark.parametrize("roh, erwartet", [
    ("The result was 47.", "The result was forty-seven."),
    ("published in 1986.", "published in nineteen eighty-six."),
    ("A 2016 study from Stanford.", "A twenty sixteen study from Stanford."),
    ("reached 13.3 points", "reached thirteen point three points"),
    ("from ITD 5, WPM INF", "from ITD five, WPM INF"),
    ("80 percent of students", "eighty percent of students"),
    ("about 1,000 participants", "about one thousand participants"),
])
def test_englische_zahlen_werden_ausgeschrieben(roh, erwartet):
    assert spell_numbers(roh, "EN") == erwartet


@pytest.mark.parametrize("sprache", ["DE", "FR", "TR", "ES"])
def test_andere_sprachen_bleiben_unangetastet(sprache):
    """Nur fuer Englisch gemessen, anderswo bleibt es wie bisher."""
    text = "Es waren 47 Personen im Jahr 1986."
    assert spell_numbers(text, sprache) == text


def test_sprachvarianten_werden_erkannt():
    assert spell_numbers("was 47.", "EN-US") == "was forty-seven."
    assert spell_numbers("was 47.", "en") == "was forty-seven."


def test_text_ohne_ziffern_bleibt_gleich():
    text = "There is nothing to convert in this sentence."
    assert spell_numbers(text, "EN") == text


def test_ohne_sprache_bleibt_der_text_in_ruhe():
    text = "The result was 47."
    assert spell_numbers(text, "xx") == text


@pytest.mark.parametrize("text", [
    "Test yourself at https://der-newstest.de/ today.",
    "See https://example.com/2016/report for details.",
    "Write to a1@example.org please.",
])
def test_adressen_bleiben_unangetastet(text):
    assert spell_numbers(text, "EN") == text


def test_ziffern_in_woertern_bleiben_stehen():
    """COVID-19 oder H2O sind Namen, keine Zahlen."""
    assert spell_numbers("The COVID-19 pandemic and H2O.", "EN") == "The COVID-19 pandemic and H2O."


def test_leerer_text_faellt_nicht_um():
    assert spell_numbers("", "EN") == ""
    assert spell_numbers(None, "EN") == ""
