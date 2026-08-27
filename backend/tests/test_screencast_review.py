"""Detects untranslated slides by plain text comparison, without language knowledge."""

from src.services.screencast.review import find_unchanged_slides


def test_changed_slide_is_not_flagged():
    assert find_unchanged_slides(["Guten Morgen zusammen"], ["Good morning everyone"]) == []


def test_identical_slide_is_flagged():
    assert find_unchanged_slides(["Kategorien für Fragen"], ["Kategorien für Fragen"]) == [0]


def test_only_whitespace_differs_is_still_flagged():
    assert find_unchanged_slides(["Ablauf der  Sitzung"], ["Ablauf\nder Sitzung"]) == [0]


def test_case_only_difference_is_flagged():
    assert find_unchanged_slides(["Ablauf der Sitzung"], ["ABLAUF DER SITZUNG"]) == [0]


def test_empty_slide_is_not_flagged():
    """An empty slide is not a translation problem."""
    assert find_unchanged_slides(["", "   "], ["", ""]) == []


def test_very_short_text_is_not_flagged():
    """Single numbers or codes are the same in every language, that is no finding."""
    assert find_unchanged_slides(["2026", "Nr. 4"], ["2026", "Nr. 4"]) == []


def test_reports_every_affected_slide():
    original = ["Einleitung und Überblick", "Zweite Folie mit Inhalt", "Dritte Folie mit Inhalt"]
    translated = ["Introduction and overview", "Zweite Folie mit Inhalt", "Third slide with content"]
    assert find_unchanged_slides(original, translated) == [1]


def test_different_lengths_do_not_crash():
    """If the slide counts diverge, that must not raise."""
    assert find_unchanged_slides(["Ein längerer Text hier"], []) == []
    assert find_unchanged_slides([], ["Ein längerer Text hier"]) == []
