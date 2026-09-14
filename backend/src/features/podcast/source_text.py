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


def to_pieces(text: str) -> list[dict]:
    """Plain text in chunk-shaped pieces, the budget picker needs units to choose from."""
    from src.services.aia_chunker import CHUNK_OVERLAP, CHUNK_SIZE, _split_text

    return [{"content": stueck} for stueck in _split_text(text, CHUNK_SIZE, CHUNK_OVERLAP)]


def from_module(workspace_uuid: str, source_uuids: list[str], user_id: int,
                locale: str = "de") -> tuple[list[tuple[str, list[dict]]], str]:
    """The indexed pieces of the chosen sources, plus a label for the job list.

    The same gate the assistant itself uses, otherwise any module uuid would do.
    """
    from src import database as db
    from src.features.ai_assistant.routes._workspace_access import _require_workspace_access

    workspace = _require_workspace_access(workspace_uuid, user_id, locale=locale)
    gewaehlt = set(source_uuids)
    quellen: list[tuple[str, list[dict]]] = []
    namen: list[str] = []
    for source in db.get_aia_sources_by_workspace(workspace["id"]):
        if source["uuid"] not in gewaehlt or source["status"] != "ready":
            continue
        namen.append(source["filename"])
        chunks = [c for c in db.get_aia_chunks_by_source(source["id"]) if c.get("content")]
        if chunks:
            quellen.append((source["filename"], chunks))
        else:
            logger.warning("Podcast: Quelle {} hat keine Abschnitte", source["uuid"])
    return quellen, ", ".join(namen)


def fit_to_budget(sources: list[tuple[str, list[dict]]]) -> str:
    """Fills the budget source by source, front to back. What does not fit is dropped.

    The order is the user's choice, so whoever wants a source used puts it first.
    """
    from src.features.ai_assistant.tasks._context_budget import tool_context_budget

    uebrig = tool_context_budget("podcast")
    teile: list[str] = []
    for label, chunks in sources:
        kopf = f"# {label}\n" if label else ""
        genommen: list[str] = []
        platz = uebrig - len(kopf)
        for chunk in chunks:
            inhalt = (chunk.get("content") or "").strip()
            if not inhalt:
                continue
            if len(inhalt) + 1 > platz:
                break
            genommen.append(inhalt)
            platz -= len(inhalt) + 1
        if not genommen:
            break
        teile.append(kopf + "\n".join(genommen))
        uebrig = platz - 2  # the blank line between two sources
    return "\n\n".join(teile)
