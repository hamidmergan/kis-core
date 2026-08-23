"""Ziffern zu Wörtern, bevor der Text an die Vertonung geht."""

import re

from loguru import logger

# Ziffernfolge mit Tausendertrennern und Nachkommastelle, freistehend als Wort.
_ZAHL = re.compile(r"(?<![\w.,/@-])(?:\d{1,3}(?:[.,]\d{3})+|\d+(?:\.\d+)?)(?![\w/@-])")

# Adressen bleiben unangetastet, dort ist eine Ziffer keine gesprochene Zahl.
_ADRESSE = re.compile(r"\S+(?:://|@)\S+|\b\S+\.(?:de|com|org|net|eu|io)\b", re.I)

# Vierstellige Zahlen in dieser Spanne werden als Jahr gesprochen.
_JAHR_VON, _JAHR_BIS = 1500, 2099

# Nur hier ist das Deutsch-Raten der Stimme gemessen, sonst bleibt alles wie bisher.
_GEMESSENE_SPRACHEN = {"en"}


def _sprachcode(language: str) -> str:
    """Aus "EN-US" wird "en"."""
    return (language or "").strip().replace("_", "-").split("-")[0].lower()


def _als_wort(roh: str, lang: str) -> str:
    from num2words import num2words

    text = roh.replace(",", "") if re.fullmatch(r"\d{1,3}(?:,\d{3})+", roh) else roh
    text = text.replace(".", "") if re.fullmatch(r"\d{1,3}(?:\.\d{3})+", roh) else text
    zahl = float(text) if "." in text else int(text)
    if isinstance(zahl, int) and _JAHR_VON <= zahl <= _JAHR_BIS and len(roh) == 4:
        return num2words(zahl, lang=lang, to="year")
    return num2words(zahl, lang=lang)


def spell_numbers(text: str, language: str) -> str:
    """Ziffern als Wörter ausschreiben, damit die Vertonung die Sprache erkennt.

    Greift nur bei Englisch, weil das Deutsch-Raten der Stimme nur dort gemessen
    ist. Jede andere Sprache geht unverändert raus.
    """
    if not text:
        return ""
    lang = _sprachcode(language)
    if lang not in _GEMESSENE_SPRACHEN:
        return text
    try:
        from num2words import CONVERTER_CLASSES
    except ImportError:
        logger.warning("num2words fehlt, Ziffern gehen unveraendert an die Vertonung")
        return text
    if lang not in CONVERTER_CLASSES:
        return text

    geschuetzt = [(m.start(), m.end()) for m in _ADRESSE.finditer(text)]

    def ersetze(treffer: re.Match) -> str:
        if any(a <= treffer.start() < b for a, b in geschuetzt):
            return treffer.group(0)
        try:
            return _als_wort(treffer.group(0), lang)
        except Exception:  # noqa: BLE001 - eine unlesbare Zahl bleibt stehen
            return treffer.group(0)

    return _ZAHL.sub(ersetze, text)
