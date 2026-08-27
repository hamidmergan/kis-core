"""Verifies the word split, every part must be findable in the term."""

import unicodedata

# Share of the part that must appear in the term, plus a floor in characters.
_MIN_ANTEIL = 0.6
_MIN_ZEICHEN = 3


def _fold(text: str) -> str:
    """Only the bare letters: lowercased, without diacritics, without joining hyphens."""
    # casefold first, then NFKD, so umlauts and sharp s fall away.
    zerlegt = unicodedata.normalize("NFKD", text.casefold())
    return "".join(c for c in zerlegt if c.isalnum() and not unicodedata.combining(c))


def _steckt_im_begriff(begriff: str, teil: str) -> bool:
    laenge = max(_MIN_ZEICHEN, round(len(teil) * _MIN_ANTEIL))
    return bool(teil) and teil[:min(len(teil), laenge)] in begriff


def clean_word_parts(begriff: str, word_parts: str, word_parts_explained: str) -> tuple[str, str]:
    """Returns word parts and explanation, both empty when it does not hold."""
    teile = [t.strip() for t in (word_parts or "").split("+")]
    teile = [t for t in teile if t]
    # A single part is not a split but the word itself.
    if len(teile) < 2:
        return "", ""

    gefaltet = _fold(begriff)
    if not all(_steckt_im_begriff(gefaltet, _fold(t)) for t in teile):
        return "", ""

    erklaerung = (word_parts_explained or "").strip()
    # The check splits exactly the way the view reads it.
    zeilen = [z.strip() for z in erklaerung.split("|")] if erklaerung else []
    zeilen = [z for z in zeilen if z]
    passt = len(zeilen) == len(teile) and all(
        _fold(t) in _fold(z.split("=", 1)[0]) for t, z in zip(teile, zeilen)
    )
    return " + ".join(teile), (erklaerung if passt else "")
