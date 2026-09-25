"""Slide previews through the LibreOffice path the screencast already uses."""

from __future__ import annotations

import tempfile
from pathlib import Path

from src.features.praesentation import bau
from src.features.praesentation.schemas import Slide
from src.features.praesentation.vorlage import Analyse
from src.services.screencast.pptx import pptx_to_images

DPI = 80


def render(deck: bytes, dpi: int = DPI) -> list[bytes]:
    with tempfile.TemporaryDirectory(prefix="praesentation_preview_") as tmp:
        pfad = Path(tmp) / "deck.pptx"
        pfad.write_bytes(deck)
        ziel = Path(tmp) / "img"
        ziel.mkdir()
        return [p.read_bytes() for p in pptx_to_images(pfad, ziel, dpi=dpi)]


def einzeln(vorlage_bytes: bytes, a: Analyse, slide: Slide, bilder: dict[str, bytes],
            titel: str, notizen: bool, hinweis: str = "", nummer: int = 1, datum: str = "",
            vortragend: str = "") -> bytes:
    """One slide as a one-slide deck, so a single edit never renders the whole deck."""
    return mehrere(vorlage_bytes, a, [slide], bilder, titel, notizen, hinweis, nummern=[nummer], datum=datum,
                   vortragend=vortragend)[0]


def mehrere(vorlage_bytes: bytes, a: Analyse, slides: list[Slide], bilder: dict[str, bytes],
            titel: str, notizen: bool, hinweis: str = "", *, nummern: list[int],
            datum: str = "", vortragend: str = "") -> list[bytes]:
    """Some slides of the deck in one render, each under its own number."""
    deck = bau.baue(vorlage_bytes, a, slides, bilder, titel, notizen, hinweis, nummern=nummern, datum=datum,
                    vortragend=vortragend)
    bilder_png = render(deck)
    if len(bilder_png) < len(slides):
        raise RuntimeError("LibreOffice lieferte kein Vorschaubild")
    return bilder_png[:len(slides)]
