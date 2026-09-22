"""One uploaded file into the canonical text of a run, with its pieces and their places.

What comes out of here is the single truth about a source for the rest of the run. The
text is produced once and never derived again, because every position a fact later
carries is a position in exactly this text.
"""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path

from loguru import logger

from src.services.pdf_layout import (
    boilerplate_keys,
    is_boilerplate,
    line_boxes,
    merge_rows,
    page_reading_order,
    strip_boilerplate_text,
)
from src.services.text_pieces import PIECE_CHARS, PIECE_OVERLAP, clean, split_spans

# What a page break looks like in the assembled text.
_PAGE_BREAK = "\n\n"

# Subtitles are in here because a transcript is a document like any other.
EXTENSIONS: tuple[str, ...] = (".pdf", ".txt", ".md", ".docx", ".pptx", ".srt", ".vtt")


class NoReadableText(ValueError):
    """The file carries no text at all, a scan without a text layer for instance."""


@dataclass(frozen=True)
class Piece:
    """One piece of the text and where it sits, counted in the text of this source."""

    seite: int
    von: int
    bis: int


@dataclass(frozen=True)
class Source:
    """A read file as the rest of the run sees it."""

    dateiname: str
    # Checksum of the original file, so stored facts can be dropped when it changes.
    fassung: str
    text: str
    stuecke: list[Piece]
    seiten: int

    def as_dict(self) -> dict:
        return {
            "dateiname": self.dateiname,
            "fassung": self.fassung,
            "text": self.text,
            "seiten": self.seiten,
            "stuecke": [asdict(s) for s in self.stuecke],
        }


def from_dict(daten: dict) -> Source:
    """A source back out of the job folder, the counterpart of ``as_dict``."""
    stuecke = [Piece(seite=int(s["seite"]), von=int(s["von"]), bis=int(s["bis"]))
               for s in daten.get("stuecke") or []]
    return Source(
        dateiname=str(daten.get("dateiname") or ""),
        fassung=str(daten.get("fassung") or ""),
        text=str(daten.get("text") or ""),
        stuecke=stuecke,
        seiten=int(daten.get("seiten") or 0),
    )


def _fassung(path: str) -> str:
    """The checksum of the file as it was uploaded, before anything touched it."""
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            hasher.update(block)
    return hasher.hexdigest()


def _pdf_pages(path: str) -> list[str]:
    """Every page of a PDF as cleaned text, headers and footers counted out.

    No text recognition: a page without a text layer stays empty and the caller
    refuses the file rather than guessing at a picture.
    """
    import pypdfium2 as pdfium

    seiten_text: list[str] = []
    seiten_kaesten: list[list] = []
    doc = pdfium.PdfDocument(path)
    try:
        for nummer in range(len(doc)):
            seite = doc[nummer]
            textpage = seite.get_textpage()
            seiten_text.append(clean(textpage.get_text_range() or "").strip())
            seiten_kaesten.append(line_boxes(textpage))
            textpage.close()
            seite.close()
    finally:
        doc.close()

    # Counted over the whole document, a header only shows itself in the whole.
    boiler = boilerplate_keys(seiten_kaesten, seiten_text)
    aus: list[str] = []
    for kaesten, roh in zip(seiten_kaesten, seiten_text):
        geordnet = page_reading_order([b for b in kaesten if not is_boilerplate(b.text, boiler)])
        zeilen = merge_rows(geordnet)
        aus.append("\n".join(b.text for b in zeilen) if zeilen
                   else strip_boilerplate_text(roh, boiler))
    logger.info("Quelle {}: {} Seite(n), {} Kopf- oder Fusszeile(n) entfernt",
                Path(path).name, len(aus), len(boiler))
    return aus


def _other_pages(path: str, ext: str) -> list[str]:
    """Every other format as one single page, they carry no page numbers worth keeping."""
    from src.utils.text_extraction import EXTRACTORS

    leser = EXTRACTORS.get(ext)
    if leser is None:
        raise ValueError(f"Format {ext} wird nicht unterstuetzt")
    return [clean(leser(path) or "").strip()]


def _assemble(seiten: list[str]) -> tuple[str, list[tuple[int, int, int]]]:
    """The pages as one text, plus where each page starts and ends in it.

    An empty page keeps its number but takes no room, so the page of a piece stays
    right even in a document with blank pages in the middle.
    """
    teile: list[str] = []
    grenzen: list[tuple[int, int, int]] = []
    stelle = 0
    for nummer, roh in enumerate(seiten, start=1):
        # Gestrippt, sonst zaehlt fuehrender Leerraum als Seiteninhalt mit.
        seite = roh.strip()
        if not seite:
            continue
        if teile:
            stelle += len(_PAGE_BREAK)
        grenzen.append((nummer, stelle, stelle + len(seite)))
        teile.append(seite)
        stelle += len(seite)
    return _PAGE_BREAK.join(teile), grenzen


def _seite_von(stelle: int, grenzen: list[tuple[int, int, int]]) -> int:
    """The page a position sits on, the page it starts on when a piece spans two."""
    for nummer, von, bis in grenzen:
        if von <= stelle < bis:
            return nummer
    return grenzen[-1][0] if grenzen else 1


def _pieces(text: str, grenzen: list[tuple[int, int, int]]) -> list[Piece]:
    """The text cut into pieces, each one knowing its page and its place."""
    return [Piece(seite=_seite_von(von, grenzen), von=von, bis=bis)
            for von, bis in split_spans(text, PIECE_CHARS, PIECE_OVERLAP)]


def read_file(path: str, dateiname: str) -> Source:
    """One file to the canonical source record. Raises when it carries no text."""
    ext = Path(dateiname).suffix.lower()
    if ext not in EXTENSIONS:
        raise ValueError(f"Format {ext} wird nicht unterstuetzt")
    seiten = _pdf_pages(path) if ext == ".pdf" else _other_pages(path, ext)
    text, grenzen = _assemble(seiten)
    if not text.strip():
        raise NoReadableText(dateiname)
    stuecke = _pieces(text, grenzen)
    logger.info("Quelle {}: {} Zeichen, {} Stueck(e)", dateiname, len(text), len(stuecke))
    return Source(dateiname=dateiname, fassung=_fassung(path), text=text,
                  stuecke=stuecke, seiten=len(seiten))


def from_text(dateiname: str, text: str) -> Source:
    """A text with no document behind it, a transcript for instance.

    It becomes the same record a file becomes, so nothing downstream can tell the two
    apart. There are no page numbers to keep, and the fingerprint comes from the text
    itself because there is no original to weigh.
    """
    ganz, grenzen = _assemble([clean(text or "")])
    if not ganz.strip():
        raise NoReadableText(dateiname)
    stuecke = _pieces(ganz, grenzen)
    logger.info("Quelle {}: {} Zeichen, {} Stueck(e), aus Text", dateiname, len(ganz), len(stuecke))
    return Source(dateiname=dateiname,
                  fassung=hashlib.sha256(ganz.encode("utf-8")).hexdigest(),
                  text=ganz, stuecke=stuecke, seiten=1)
