"""Erkennung unübersetzter Folien für den Prüfen-Schritt.

Im Prüfen-Schritt sieht man nur Vorschaubilder in Briefmarkengröße. Ob eine
Folie übersetzt wurde, ist darauf nicht zu erkennen. Genau daran sind einzelne
Folien durchgerutscht.

Der Vergleich läuft ohne Sprachkenntnis: Originaltext gegen übersetzten Text.
Sind beide gleich, hat die Übersetzung an dieser Folie nichts geändert. Das
kann harmlos sein, etwa bei Zahlen oder Eigennamen, ist aber der einzige
Hinweis, den man sprachunabhängig geben kann.
"""

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
    """Eine leere Folie ist kein Übersetzungsproblem."""
    assert find_unchanged_slides(["", "   "], ["", ""]) == []


def test_very_short_text_is_not_flagged():
    """Einzelne Zahlen oder Kürzel sind in jeder Sprache gleich, das ist kein Fund."""
    assert find_unchanged_slides(["2026", "Nr. 4"], ["2026", "Nr. 4"]) == []


def test_reports_every_affected_slide():
    original = ["Einleitung und Überblick", "Zweite Folie mit Inhalt", "Dritte Folie mit Inhalt"]
    translated = ["Introduction and overview", "Zweite Folie mit Inhalt", "Third slide with content"]
    assert find_unchanged_slides(original, translated) == [1]


def test_different_lengths_do_not_crash():
    """Kommt die Folienzahl auseinander, darf das keine Ausnahme werfen."""
    assert find_unchanged_slides(["Ein längerer Text hier"], []) == []
    assert find_unchanged_slides([], ["Ein längerer Text hier"]) == []
