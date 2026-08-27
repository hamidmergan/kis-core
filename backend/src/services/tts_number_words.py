"""Digits to words before the text goes to the voicing."""

import re

from loguru import logger

# Digit sequence with thousands separators and a decimal, standing alone as a word.
_ZAHL = re.compile(r"(?<![\w.,/@-])(?:\d{1,3}(?:[.,]\d{3})+|\d+(?:\.\d+)?)(?![\w/@-])")

# Addresses stay untouched, a digit there is not a spoken number.
_ADRESSE = re.compile(r"\S+(?:://|@)\S+|\b\S+\.(?:de|com|org|net|eu|io)\b", re.I)

# Four-digit numbers in this range are spoken as a year.
_JAHR_VON, _JAHR_BIS = 1500, 2099

# Only here is the voice's German guessing measured, elsewhere nothing changes.
_GEMESSENE_SPRACHEN = {"en"}


def _sprachcode(language: str) -> str:
    """'EN-US' becomes 'en'."""
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
    """Spells digits out as words, English only."""
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
