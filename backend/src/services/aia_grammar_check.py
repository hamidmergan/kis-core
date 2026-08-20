"""Prüfung einer Freitext-Antwort in der Grammatik-Übung.

Reiner Vergleich, kein Modell-Aufruf. Verglichen wird gegen die Musterlösung und
gegen die gültigen Zweitfassungen, die schon beim Erzeugen der Aufgabe entstanden
sind. Die Erklärung hängt ebenfalls seit dem Erzeugen an der Aufgabe.

Vorher lief bei jeder abweichenden Antwort ein Modell-Aufruf. Er urteilte gut, war
aber der teuerste Weg zu einer Rückmeldung, die es schon gab.

Die Normalisierung ist bewusst sprach-unabhängig: kein Wörterbuch, keine deutschen
Sonderregeln, nur Unicode-Kategorien.
"""

import re
import unicodedata

VERDICT_CORRECT = "correct"
VERDICT_CLOSE = "close"
VERDICT_WRONG = "wrong"

# Ab dieser Wortüberdeckung gilt eine Antwort im Notfallpfad als "fast".
_CLOSE_RATIO = 0.72

# Klammereinschübe sind im Muster optional ("Die Briefe müssen (von mir) ...").
# Wer sie weglässt, hat trotzdem recht, also fliegen sie vor dem Vergleich raus.
_PARENS_RE = re.compile(r"\([^)]*\)")
_WS_RE = re.compile(r"\s+")


def normalize(text: str) -> str:
    """Vergleichsform: klein, ohne Klammereinschübe, ohne Satzzeichen."""
    if not text:
        return ""
    cleaned = _PARENS_RE.sub(" ", text)
    # Unicode-Kategorie P* sind alle Satzzeichen, in jeder Sprache.
    cleaned = "".join(
        " " if unicodedata.category(ch).startswith("P") else ch
        for ch in cleaned
    )
    return _WS_RE.sub(" ", cleaned).strip().casefold()


def is_exact_match(given: str, expected: str) -> bool:
    """True wenn die Antwort nach Normalisierung der Musterlösung entspricht."""
    normalized = normalize(given)
    return bool(normalized) and normalized == normalize(expected)


def overlap_ratio(given: str, expected: str) -> float:
    """Anteil gemeinsamer Wörter, Vielfachheit berücksichtigt. 0.0 bis 1.0."""
    a = normalize(given).split()
    b = normalize(expected).split()
    if not a or not b:
        return 0.0
    pool = list(b)
    hits = 0
    for word in a:
        if word in pool:
            pool.remove(word)
            hits += 1
    return hits / max(len(a), len(b))


def mark_answer(given: str, expected: str, accepts=()) -> str:
    """Urteil zu einer Antwort: richtig, fast oder falsch.

    ``accepts`` sind weitere gültige Fassungen derselben Umformung. Grammatik hat
    selten genau eine Lösung ("Das Smartphone wäre ..." und "Das Smartphone würde
    ... sein" sind beide richtig), und ohne sie bekäme ein Lernender für eine
    richtige Antwort ein Rot. Sie entstehen beim Erzeugen der Aufgabe mit.

    "Fast" wird an der nächstliegenden Fassung gemessen, nicht immer an der
    Musterlösung: wer eine Zweitfassung knapp verfehlt, hat sie knapp verfehlt.
    """
    candidates = [expected, *accepts]
    if any(is_exact_match(given, c) for c in candidates):
        return VERDICT_CORRECT
    best = max(overlap_ratio(given, c) for c in candidates)
    return VERDICT_CLOSE if best >= _CLOSE_RATIO else VERDICT_WRONG


__all__ = [
    "VERDICT_CORRECT", "VERDICT_CLOSE", "VERDICT_WRONG",
    "normalize", "is_exact_match", "overlap_ratio", "mark_answer",
]
