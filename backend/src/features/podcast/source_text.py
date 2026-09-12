"""Where the material comes from: typed text, uploaded files or a module."""

from pathlib import Path

from loguru import logger

from src.utils.text_extraction import EXTRACTORS

# PDF is not in the shared table, the assistant reads it with its heavy machinery.
PODCAST_EXTENSIONS: tuple[str, ...] = (".txt", ".md", ".docx", ".pptx", ".pdf")


def extract_pdf(path: str) -> str:
    """A lean read without OCR, enough for a podcast about a readable document."""
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(path)
    try:
        seiten = [doc[i].get_textpage().get_text_range().strip() for i in range(len(doc))]
    finally:
        doc.close()
    return "\n\n".join(s for s in seiten if s)


def extract_file(path: str, ext: str) -> str:
    """One uploaded file to plain text, empty when the format has no reader."""
    if ext == ".pdf":
        return extract_pdf(path)
    reader = EXTRACTORS.get(ext)
    return reader(path) if reader else ""


def from_module(workspace_uuid: str, source_uuids: list[str], user_id: int,
                locale: str = "de") -> tuple[str, str]:
    """The indexed text of the chosen sources, plus a label for the job list.

    The same gate the assistant itself uses, otherwise any module uuid would do.
    """
    from src import database as db
    from src.features.ai_assistant.routes._workspace_access import _require_workspace_access

    workspace = _require_workspace_access(workspace_uuid, user_id, locale=locale)
    gewaehlt = set(source_uuids)
    teile: list[str] = []
    namen: list[str] = []
    for source in db.get_aia_sources_by_workspace(workspace["id"]):
        if source["uuid"] not in gewaehlt or source["status"] != "ready":
            continue
        namen.append(source["filename"])
        chunks = db.get_aia_chunks_by_source(source["id"])
        text = "\n".join(c["content"].strip() for c in chunks if c.get("content"))
        if text:
            teile.append(f"# {source['filename']}\n{text}")
        else:
            logger.warning("Podcast: Quelle {} hat keine Abschnitte", source["uuid"])
    return "\n\n".join(teile), ", ".join(namen)


def shorten(text: str, max_chars: int) -> str:
    """Over the budget the tail is dropped, cut at a paragraph where possible."""
    if len(text) <= max_chars:
        return text
    schnitt = text.rfind("\n\n", 0, max_chars)
    return text[: schnitt if schnitt > max_chars // 2 else max_chars].rstrip()
