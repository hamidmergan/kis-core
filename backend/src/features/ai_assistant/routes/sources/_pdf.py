"""PDF-specific operations: TOC, text search."""
from ._shared import (
    Path, APIRouter, Depends, HTTPException, logger, db,
    get_current_user, get_locale, t,
    get_file,
)

router = APIRouter(tags=["ki-assistent: sources"])


@router.get("/ai-assistant/workspaces/{workspace_uuid}/sources/{source_uuid}/toc")
async def get_pdf_toc(
    workspace_uuid: str,
    source_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Return the stored table of contents from the DB."""
    user_id = current_user["user_id"]
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))

    is_owner = workspace["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(workspace["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail=t("workspace.accessDenied", locale))

    source = db.get_aia_source(source_uuid)
    if not source:
        raise HTTPException(status_code=404, detail=t("source.notFound", locale))

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
    workspace = db.get_aia_workspace(workspace_uuid)
    if not workspace:
        raise HTTPException(status_code=404, detail=t("workspace.notFound", locale))

    is_owner = workspace["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(workspace["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail=t("workspace.accessDenied", locale))

    source = db.get_aia_source(source_uuid)
    if not source:
        raise HTTPException(status_code=404, detail=t("source.notFound", locale))

    ext = Path(source["filename"]).suffix.lower()
    if ext != ".pdf":
        return {"matches": [], "page_width": 0, "page_height": 0}

    import pypdfium2 as pdfium
    import re
    import unicodedata

    # NFC preserves superscript chars (²,³) so they match the PDF text layer
    q_clean = unicodedata.normalize("NFC", q)
    q_clean = re.sub(r"-\r?\n\s*", "", q_clean)  # only line-break hyphens: "Lö-\nsungsansatz" → "Lösungsansatz"
    q_clean = re.sub(r"\s+", " ", q_clean).strip()

    if not q_clean:
        return {"matches": [], "page_width": 0, "page_height": 0}

    data = get_file(source["file_path"])
    doc = pdfium.PdfDocument(data)

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
        searcher = textpage.search(q_clean, match_case=False)

        try:
            while True:
                m = searcher.get_next()
                if m is None:
                    break
                start, count = m
                if count <= 0:
                    continue

                # Walk the matched chars, grouping into per-line rects.
                # pdfium uses bottom-up coords (origin bottom-left); convert to
                # display orientation (top-left origin, y0=top, y1=bottom) so
                # the frontend overlay math matches fitz's old output shape.
                line_rects: list[tuple[float, float, float, float]] = []
                cur: list[tuple[float, float, float, float]] = []
                last_bottom: float | None = None
                for i in range(start, start + count):
                    cl, cb, cr, ct = textpage.get_charbox(i, loose=True)
                    if ct <= cb:  # skip degenerate/zero-height (e.g. spaces)
                        continue
                    line_h = ct - cb
                    if last_bottom is not None and abs(cb - last_bottom) > line_h * 0.5:
                        if cur:
                            line_rects.append((
                                min(c[0] for c in cur),
                                min(c[1] for c in cur),
                                max(c[2] for c in cur),
                                max(c[3] for c in cur),
                            ))
                            cur = []
                    cur.append((cl, cb, cr, ct))
                    last_bottom = cb
                if cur:
                    line_rects.append((
                        min(c[0] for c in cur),
                        min(c[1] for c in cur),
                        max(c[2] for c in cur),
                        max(c[3] for c in cur),
                    ))

                if not line_rects:
                    continue

                rects_display = [
                    {"x0": l, "y0": ph - t, "x1": r, "y1": ph - b}
                    for (l, b, r, t) in line_rects
                ]
                matches.append({"page": page_num + 1, "rects": rects_display})
        finally:
            searcher.close()
            textpage.close()
            pg.close()

    doc.close()
    return {"matches": matches, "page_width": page_width, "page_height": page_height}
