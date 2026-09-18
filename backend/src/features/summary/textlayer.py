"""The text layer of one file as running text, the retrieval chunker is not involved."""

from src.services.aia_chunker import _clean
from src.utils.text_extraction import EXTRACTORS


class NoReadableText(ValueError):
    """A PDF whose pages carry no text at all, only pictures."""


def _open_pdf(local_path: str):
    import pypdfium2 as pdfium

    return pdfium.PdfDocument(local_path)


def _pdf_text(local_path: str) -> str:
    """Every page's text layer, pages separated by a blank line, empty pages dropped."""
    doc = _open_pdf(local_path)
    seiten = []
    try:
        for i in range(len(doc)):
            text = _clean(doc[i].get_textpage().get_text_range() or "").strip()
            if text:
                seiten.append(text)
    finally:
        doc.close()
    if not seiten:
        raise NoReadableText(local_path)
    return "\n\n".join(seiten)


def read_text_layer(local_path: str, ext: str) -> str:
    """The whole text of a file, nothing cut and nothing repeated."""
    endung = f".{ext.lower().lstrip('.')}"
    if endung == ".pdf":
        return _pdf_text(local_path)
    extractor = EXTRACTORS.get(endung)
    if extractor is None:
        raise ValueError(f"Format {endung} wird nicht unterstuetzt")
    return extractor(local_path)
