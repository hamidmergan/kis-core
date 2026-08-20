"""Absage-Saetze der KI-Assistenz und ihre Erkennung in der Antwort."""

import re

from src.i18n import DEFAULT_LOCALE


# Vergleichstext, an dem eine Absage in jeder Sprache am Abstand erkannt wird.
RAG_NO_INFO_SENTINEL: dict[str, str] = {
    "de": "Diese Information ist nicht in den bereitgestellten Materialien enthalten.",
    "en": "This information is not contained in the provided sources.",
}

# Sicherheitsnetz fuer die alte Wendung, die das Modell aus Gewohnheit noch schreibt.
_GAP_ANCHORS: tuple[str, ...] = (
    "steht nicht in den materialien",
    "stehen nicht in den materialien",
    "steht nicht in den quellen",
    "stehen nicht in den quellen",
    "is not in the sources",
    "are not in the sources",
)

# Rahmen fuer den Fall, dass das Modell nur den fehlenden Begriff nennt statt eines Satzes.
_GAP_FRAME: dict[str, str] = {
    "de": "In den Materialien steht nichts zu \u201e{begriff}\u201c",
    "en": "The sources say nothing about \"{begriff}\"",
}

# Erstes Wort der Bruecke, denn die Antwort folgt der Frage und nicht der Oberflaeche.
_BRIDGE_LOCALE: dict[str, str] = {
    "jedoch": "de", "allerdings": "de", "aber": "de", "dafuer": "de", "daf\u00fcr": "de",
    "however": "en", "but": "en", "yet": "en", "instead": "en", "although": "en",
}

# Ein Satz hat ein Satzende, ein nackt genannter Begriff hat keines.
_SATZENDE = ".!?"

# Mehr Woerter als das schreibt niemand als blosse Benennung.
_MAX_BEGRIFF_WOERTER = 4

# Anfuehrungs- und Randzeichen, die der Rahmen selbst setzt und darum vorher abfallen.
_TERM_TRIM = " \t\r\n\"'\u201c\u201d\u201e\u00ab\u00bb.,:;!?"

# Rand-Zeichen, die vor dem Vergleich abfallen.
_SENTINEL_TRIM = " \t\r\n*_`\"'“”„«».!"

# Satzende mit Nachfolger, grob mit Absicht.
_MORE_THAN_ONE_SENTENCE = re.compile(r"[.!?][\"'”’)\]]?\s+[^\Wa-z\d_]", re.UNICODE)


def _sentinel_key(text: str | None) -> str:
    """Vergleichsform eines Satzes: Leerraum vereinheitlicht, Rand-Zeichen ab, klein."""
    return " ".join((text or "").split()).strip(_SENTINEL_TRIM).casefold()


def refusal_reference_texts() -> list[str]:
    """Die Saetze, gegen die per Einbettung gemessen wird, absichtlich nur einer."""
    return list(RAG_NO_INFO_SENTINEL.values())


def is_gap_line(text: str | None) -> bool:
    """True, wenn diese Zeile eine Absage ist und darum KEINEN Quellenchip bekommt."""
    key = _sentinel_key(text)
    return bool(key) and any(anchor in key for anchor in _GAP_ANCHORS)


def is_sentinel_refusal(text: str | None) -> bool:
    """True, wenn die GANZE Antwort nur die Absage ist und die Nachbearbeitung entfaellt."""
    key = _sentinel_key(text)
    if not key:
        return False
    if any(key == _sentinel_key(s) for s in RAG_NO_INFO_SENTINEL.values()):
        return True
    if _MORE_THAN_ONE_SENTENCE.search(" ".join((text or "").split())):
        return False
    return is_gap_line(text)


def is_bare_term(text: str | None) -> bool:
    """True, wenn hier nur der fehlende Begriff steht und kein ganzer Satz."""
    kern = (text or "").strip()
    return bool(kern) and kern[-1] not in _SATZENDE and len(kern.split()) <= _MAX_BEGRIFF_WOERTER


def gap_locale(bridge: str | None, fallback: str = DEFAULT_LOCALE) -> str:
    """Die Sprache des Absage-Satzes, abgelesen am Bindewort der Bruecke."""
    wort = (bridge or "").strip().split(" ")[0].strip(_TERM_TRIM).casefold()
    return _BRIDGE_LOCALE.get(wort, (fallback or DEFAULT_LOCALE).lower())


def gap_sentence(term: str, locale: str = DEFAULT_LOCALE) -> str:
    """Baut aus einem nackt genannten Begriff den Absage-Satz der Antwortsprache."""
    rahmen = _GAP_FRAME.get((locale or "").lower(), _GAP_FRAME[DEFAULT_LOCALE])
    return rahmen.format(begriff=term.strip(_TERM_TRIM))
