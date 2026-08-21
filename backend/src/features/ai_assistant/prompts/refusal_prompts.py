"""Absage-Saetze der KI-Assistenz und ihre Erkennung in der Antwort."""

import re

from src.i18n import DEFAULT_LOCALE


# Vergleichstext, an dem eine Absage in jeder Sprache am Abstand erkannt wird.
RAG_NO_INFO_SENTINEL: dict[str, str] = {
    "de": "Diese Information ist nicht in den bereitgestellten Materialien enthalten.",
    "en": "This information is not contained in the provided sources.",
}

# Sprache des einen Ankers, gegen den per Abstand gemessen wird.
_MESS_LOCALE = "de"

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

# Bindewoerter, die das Modell an den Anfang der Bruecke setzt, je Sprache.
_BRIDGE_LOCALE: dict[str, str] = {
    "jedoch": "de", "allerdings": "de", "aber": "de", "dafuer": "de", "daf\u00fcr": "de",
    "however": "en", "but": "en", "yet": "en", "instead": "en", "although": "en",
}

# Das Bindewort, das der Code setzt, wenn das Modell eines der anderen Sprache nimmt.
_BRIDGE_CANON: dict[str, str] = {"de": "jedoch", "en": "however"}

# Funktionswoerter, die Deutsch und Englisch ohne Ueberschneidung voneinander trennen.
_SPRACHMARKEN: dict[str, frozenset[str]] = {
    "de": frozenset({
        "der", "die", "das", "den", "dem", "des", "ein", "eine", "einen", "einem",
        "nicht", "nichts", "kein", "keine", "keinen", "und", "ist", "sind", "wird",
        "werden", "steht", "stehen", "sie", "auch", "doch", "sich", "mit", "wie",
        "was", "wann", "zu", "zum", "zur", "im", "am", "materialien", "unterlagen",
        "quellen",
    }),
    "en": frozenset({
        "the", "sources", "say", "says", "nothing", "about", "is", "are", "not",
        "and", "of", "they", "it", "to", "does", "do", "materials", "documents",
        "this", "that", "there", "what", "when", "where", "which", "for", "with",
    }),
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

# Erstes Wort einer Zeichenkette, Ziffern und Satzzeichen zaehlen nicht als Wort.
_ERSTES_WORT = re.compile(r"\s*([^\W\d_]+)", re.UNICODE)


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
    """True, wenn hier nur der fehlende Begriff steht und kein ganzer Satz."""
    kern = (text or "").strip()
    return bool(kern) and kern[-1] not in _SATZENDE and len(kern.split()) <= _MAX_BEGRIFF_WOERTER


def _bindewort(bridge: str | None) -> tuple[str, int, int]:
    """Das erste Wort der Bruecke, klein geschrieben, mit seinen Randstellen im Text."""
    treffer = _ERSTES_WORT.match(bridge or "")
    if not treffer:
        return "", 0, 0
    return treffer.group(1).casefold(), treffer.start(1), treffer.end(1)


def answer_locale(gap: str | None, bridge: str | None, fallback: str = DEFAULT_LOCALE) -> str:
    """Die Sprache der Absage, gemessen an der Prosa und erst danach am Bindewort."""
    wort, _, ende = _bindewort(bridge)
    # Genau dieses Wort ist der Kandidat fuer den Fehlgriff, also zaehlt es nicht mit.
    rest = (bridge or "")[ende:] if wort in _BRIDGE_LOCALE else (bridge or "")
    woerter = {w.strip(_TERM_TRIM).casefold() for w in f"{gap or ''} {rest}".split()}
    treffer = sorted(
        ((len(woerter & marken), code) for code, marken in _SPRACHMARKEN.items()),
        reverse=True,
    )
    if treffer[0][0] > treffer[1][0]:
        return treffer[0][1]
    return _BRIDGE_LOCALE.get(wort, (fallback or DEFAULT_LOCALE).lower())


def align_bridge(bridge: str | None, locale: str) -> str:
    """Tauscht ein Bindewort aus der falschen Sprache gegen das der Antwortsprache."""
    text = bridge or ""
    ziel = _BRIDGE_CANON.get((locale or "").lower())
    wort, start, ende = _bindewort(text)
    quelle = _BRIDGE_LOCALE.get(wort)
    if not ziel or not quelle or quelle == (locale or "").lower():
        return text
    return text[:start] + ziel + text[ende:]


def gap_sentence(term: str, locale: str = DEFAULT_LOCALE) -> str:
    """Baut aus einem nackt genannten Begriff den Absage-Satz der Antwortsprache."""
    rahmen = _GAP_FRAME.get((locale or "").lower(), _GAP_FRAME[DEFAULT_LOCALE])
    return rahmen.format(begriff=term.strip(_TERM_TRIM))
