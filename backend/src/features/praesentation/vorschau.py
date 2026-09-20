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
            titel: str, notizen: bool, hinweis: str = "") -> bytes:
    """One slide as a one-slide deck, so a single edit never renders the whole deck."""
    deck = bau.baue(vorlage_bytes, a, [slide], bilder, titel, notizen, hinweis)
    bilder_png = render(deck)
    if not bilder_png:
        raise RuntimeError("LibreOffice lieferte kein Vorschaubild")
    return bilder_png[0]
