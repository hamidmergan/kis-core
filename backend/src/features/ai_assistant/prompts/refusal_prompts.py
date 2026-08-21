"""Absage-Saetze der KI-Assistenz und ihre Erkennung in der Antwort."""

import re


# Woertlich verglichener Absage-Satz, zugleich der Anker fuer den Abstand.
RAG_NO_INFO_SENTINEL: dict[str, str] = {
    "de": "Diese Information ist nicht in den bereitgestellten Materialien enthalten.",
}

# Sprache des einen Ankers, gegen den per Abstand gemessen wird.
_MESS_LOCALE = "de"

# Sicherheitsnetz fuer die alte Wendung, die das Modell aus Gewohnheit noch schreibt.
_GAP_ANCHORS: tuple[str, ...] = (
    "steht nicht in den materialien",
    "stehen nicht in den materialien",
    "steht nicht in den quellen",
    "stehen nicht in den quellen",
)

# Ein Satz hat ein Satzende, ein nackt genannter Begriff hat keines.
_SATZENDE = ".!?"

# Mehr Woerter als das schreibt niemand als blosse Benennung.
_MAX_BEGRIFF_WOERTER = 4

# Rand-Zeichen, die vor dem Vergleich abfallen.
_SENTINEL_TRIM = " \t\r\n*_`\"'“”„«».!"

# Satzende mit Nachfolger, grob mit Absicht.
_MORE_THAN_ONE_SENTENCE = re.compile(r"[.!?][\"'”’)\]]?\s+[^\Wa-z\d_]", re.UNICODE)


def _sentinel_key(text: str | None) -> str:
    """Vergleichsform eines Satzes: Leerraum vereinheitlicht, Rand-Zeichen ab, klein."""
    return " ".join((text or "").split()).strip(_SENTINEL_TRIM).casefold()


def refusal_reference_texts() -> list[str]:
    """Der Satz, gegen den per Einbettung gemessen wird, gemessen genuegt der deutsche."""
    return [RAG_NO_INFO_SENTINEL[_MESS_LOCALE]]


def is_only_gap(answer: str | None, gap: str | None) -> bool:
    """True, wenn die ganze Antwort nur der Absage-Satz aus dem Feld ``gap`` ist."""
    schluessel = _sentinel_key(gap)
    return bool(schluessel) and _sentinel_key(answer) == schluessel


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
    """True, wenn hier nur der Begriff steht statt eines Satzes, nur zum Melden."""
    kern = (text or "").strip()
    return bool(kern) and kern[-1] not in _SATZENDE and len(kern.split()) <= _MAX_BEGRIFF_WOERTER
