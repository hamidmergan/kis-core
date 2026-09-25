"""The Phosphor Regular icons a card may carry, tinted in the template's colour on the way in."""

from __future__ import annotations

import functools
import re
from io import BytesIO
from pathlib import Path

from PIL import Image

ORDNER = Path(__file__).parent / "icons"
# What a card shows when the model names an icon outside the list.
ERSATZ = "check-circle"


@functools.lru_cache(maxsize=1)
def namen() -> tuple[str, ...]:
    return tuple(sorted(p.stem for p in ORDNER.glob("*.png")))


def gueltig(name: str) -> str:
    """The icon's name in the list's spelling, or the neutral one when it is not there."""
    schluessel = re.sub(r"[\s_]+", "-", str(name or "").strip().lower())
    return schluessel if schluessel in namen() else ERSATZ


@functools.lru_cache(maxsize=256)
def _getoent(name: str, farbe: str) -> bytes:
    maske = Image.open(ORDNER / f"{name}.png").getchannel("A")
    bild = Image.new("RGBA", maske.size, "#" + farbe)
    bild.putalpha(maske)
    out = BytesIO()
    bild.save(out, format="PNG", optimize=True)
    return out.getvalue()


def bild(name: str, farbe: str) -> BytesIO:
    """The icon as a PNG in the given hex colour, sharp enough for a full-screen projection."""
    return BytesIO(_getoent(gueltig(name), farbe.upper()))
