"""Hilfen für den Prüfen-Schritt: Folien finden, an denen die Übersetzung nichts geändert hat."""

import re

# Unter dieser Menge an Buchstaben und Ziffern lohnt der Vergleich nicht.
# Eine Jahreszahl oder ein Kürzel ist in jeder Sprache gleich.
_MIN_SIGNIFICANT_CHARS = 8

_WHITESPACE = re.compile(r"\s+")


def _normalize(text: str) -> str:
    return _WHITESPACE.sub(" ", text).strip().casefold()


def _is_significant(text: str) -> bool:
    return sum(1 for c in text if c.isalnum()) >= _MIN_SIGNIFICANT_CHARS


def find_unchanged_slides(original_texts: list[str], translated_texts: list[str]) -> list[int]:
    """Folien, deren Text die Übersetzung unverändert gelassen hat.

    Rein zeichenbasiert, damit es in jeder Sprachrichtung funktioniert. Das
    Ergebnis ist ein Hinweis, kein Urteil: Eigennamen, Zahlen und Fachbegriffe
    bleiben zu Recht gleich. Der Prüfen-Schritt zeigt es deshalb als Markierung
    an und blockiert nichts.
    """
    flagged: list[int] = []
    for index, (original, translated) in enumerate(zip(original_texts, translated_texts)):
        normalized = _normalize(original)
        if not _is_significant(normalized):
            continue
        if normalized == _normalize(translated):
            flagged.append(index)
    return flagged
