"""Absage-Saetze der KI-Assistenz und ihre Erkennung in der Antwort."""

import re


# Vergleichstext, an dem eine Absage in jeder Sprache am Abstand erkannt wird.
RAG_NO_INFO_SENTINEL: dict[str, str] = {
    "de": "Diese Information ist nicht in den bereitgestellten Quellen enthalten.",
    "en": "This information is not contained in the provided sources.",
}

# Sicherheitsnetz fuer die alte Wendung, die das Modell aus Gewohnheit noch schreibt.
_GAP_ANCHORS: tuple[str, ...] = (
    "steht nicht in den quellen",
    "stehen nicht in den quellen",
    "is not in the sources",
    "are not in the sources",
)

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
