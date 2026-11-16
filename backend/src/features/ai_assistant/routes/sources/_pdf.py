"""PDF-specific operations: TOC, text search."""
import asyncio
import re
import unicodedata

from ._shared import (
    Path, APIRouter, Depends, get_current_user,
    get_locale, get_file,
    _load_workspace_source,
)

from src.utils.pdfium_lock import PDFIUM_LOCK
from src.features.ai_assistant.routes._workspace_access import _require_workspace_member

router = APIRouter(tags=["ki-assistent: sources"])


_NO_MATCHES = {"matches": [], "page_width": 0, "page_height": 0}


def _union(boxes: list[tuple[float, float, float, float]]) -> tuple[float, float, float, float]:
    """The smallest box around the character boxes of one line."""
    return (min(c[0] for c in boxes), min(c[1] for c in boxes),
            max(c[2] for c in boxes), max(c[3] for c in boxes))


def _line_rects(textpage, start: int, count: int) -> list[tuple[float, float, float, float]]:
    """One box per text line of a match, a match may run over several lines."""
    rects: list[tuple[float, float, float, float]] = []
    cur: list[tuple[float, float, float, float]] = []
    last_bottom: float | None = None
    for i in range(start, start + count):
        cl, cb, cr, ct = textpage.get_charbox(i, loose=True)
        if ct <= cb:  # skip degenerate/zero-height (e.g. spaces)
            continue
        if last_bottom is not None and abs(cb - last_bottom) > (ct - cb) * 0.5 and cur:
            rects.append(_union(cur))
            cur = []
        cur.append((cl, cb, cr, ct))
        last_bottom = cb
    if cur:
        rects.append(_union(cur))
    return rects


def _find_matches(data, needle: str) -> dict:
    """Every place the text occurs in the PDF, the caller holds the pdfium lock."""
    import pypdfium2 as pdfium

    doc = pdfium.PdfDocument(data)
    try:
        matches: list[dict] = []
        page_width = 0.0
        page_height = 0.0
        for page_num in range(len(doc)):
            pg = doc[page_num]
            pw, ph = pg.get_size()
            if page_width == 0:
                page_width = pw
                page_height = ph

            textpage = pg.get_textpage()
            searcher = textpage.search(needle, match_case=False)
            try:
                while True:
                    m = searcher.get_next()
                    if m is None:
                        break
                    start, count = m
                    if count <= 0:
                        continue
                    rects = _line_rects(textpage, start, count)
                    if not rects:
                        continue
                    # Converts the coordinates from bottom-left to top-left.
                    matches.append({"page": page_num + 1, "rects": [
                        {"x0": l, "y0": ph - t, "x1": r, "y1": ph - b}
                        for (l, b, r, t) in rects
                    ]})
            finally:
                searcher.close()
                textpage.close()
                pg.close()
        return {"matches": matches, "page_width": page_width, "page_height": page_height}
    finally:
        doc.close()


@router.get("/ai-assistant/workspaces/{workspace_uuid}/sources/{source_uuid}/toc")
def get_pdf_toc(
    workspace_uuid: str,
    source_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Return the stored table of contents from the DB."""
    user_id = current_user["user_id"]
    workspace = _require_workspace_member(workspace_uuid, user_id, locale)

    source = _load_workspace_source(source_uuid, workspace, locale)

    return {"toc": source.get("toc") or []}


@router.get("/ai-assistant/workspaces/{workspace_uuid}/sources/{source_uuid}/search")
async def search_pdf(
    workspace_uuid: str,
    source_uuid: str,
    q: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    user_id = current_user["user_id"]
    workspace = _require_workspace_member(workspace_uuid, user_id, locale)

    source = _load_workspace_source(source_uuid, workspace, locale)

    ext = Path(source["filename"]).suffix.lower()
    if ext != ".pdf":
        return dict(_NO_MATCHES)

    # NFC preserves superscript chars (²,³) so they match the PDF text layer
    q_clean = unicodedata.normalize("NFC", q)
    q_clean = re.sub(r"-\r?\n\s*", "", q_clean)  # only line-break hyphens: "Lö-\nsungsansatz" → "Lösungsansatz"
    q_clean = re.sub(r"\s+", " ", q_clean).strip()

    if not q_clean:
        return dict(_NO_MATCHES)

    # Runs in a thread so the search does not block the event loop.
    def _search() -> dict:
        data = get_file(source["file_path"])
        # The download stays outside, only the pdfium part waits for the lock.
        with PDFIUM_LOCK:
            return _find_matches(data, q_clean)

    return await asyncio.to_thread(_search)
