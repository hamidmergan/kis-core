"""PDF-specific operations: TOC, paragraph summaries, text search, Markdown conversion."""
from ._shared import (
    Path, APIRouter, Depends, HTTPException, logger, db,
    get_current_user,
    USE_S3, file_exists, get_file,
    _strip_image_text_layer, _markdown_fallback,
)

router = APIRouter(tags=["ki-assistent"])


@router.get("/ki-assistent/modules/{module_uuid}/sources/{source_uuid}/toc")
async def get_pdf_toc(
    module_uuid: str,
    source_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    """Liefert das gespeicherte Inhaltsverzeichnis aus der DB."""
    user_id = current_user["user_id"]
    module = db.get_kia_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = module["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(module["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    source = db.get_kia_source(source_uuid)
    if not source:
        raise HTTPException(status_code=404, detail="Source nicht gefunden")

    return {"toc": source.get("toc") or []}


@router.get("/ki-assistent/modules/{module_uuid}/sources/{source_uuid}/summaries")
async def get_paragraph_summaries(
    module_uuid: str,
    source_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    """Return page-level summaries for the sidebar."""
    user_id = current_user["user_id"]
    module = db.get_kia_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = module["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(module["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    source = db.get_kia_source(source_uuid)
    if not source:
        raise HTTPException(status_code=404, detail="Source nicht gefunden")

    status = source.get("summaries_status", "none")
    summaries = db.get_paragraph_summaries_by_source(source["id"])
    by_page: dict[int, str] = {}
    for s in summaries:
        by_page[s["page_number"]] = s["summary"]

    return {"status": status, "pages": by_page}


@router.post("/ki-assistent/modules/{module_uuid}/sources/{source_uuid}/summaries/generate")
async def trigger_paragraph_summaries(
    module_uuid: str,
    source_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    """Manually trigger paragraph summary generation for a source."""
    user_id = current_user["user_id"]
    module = db.get_kia_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")
    if module["user_id"] != user_id:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    source = db.get_kia_source(source_uuid)
    if not source:
        raise HTTPException(status_code=404, detail="Source nicht gefunden")
    if source["file_type"] != "pdf":
        raise HTTPException(status_code=400, detail="Nur für PDF-Dateien verfügbar")

    status = source.get("summaries_status", "none")
    if status == "generating":
        return {"status": "generating"}

    # Keep existing summaries — task resumes where it left off
    db.update_kia_source_summaries_status(source_uuid, "generating")

    from src.tasks.kia_tasks import run_generate_summaries
    run_generate_summaries.delay(source_uuid)
    return {"status": "generating"}


@router.get("/ki-assistent/modules/{module_uuid}/sources/{source_uuid}/search")
async def search_pdf(
    module_uuid: str,
    source_uuid: str,
    q: str,
    current_user: dict = Depends(get_current_user),
):
    user_id = current_user["user_id"]
    module = db.get_kia_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = module["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(module["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    source = db.get_kia_source(source_uuid)
    if not source:
        raise HTTPException(status_code=404, detail="Source nicht gefunden")

    ext = Path(source["filename"]).suffix.lower()
    if ext != ".pdf":
        return {"matches": [], "page_width": 0, "page_height": 0}

    import fitz  # pymupdf
    import re
    import unicodedata

    # NFC preserves superscript chars (²,³) so they match the PDF text layer
    q_clean = unicodedata.normalize("NFC", q)
    q_clean = re.sub(r"-\r?\n\s*", "", q_clean)  # only line-break hyphens: "Lö-\nsungsansatz" → "Lösungsansatz"
    q_clean = re.sub(r"\s+", " ", q_clean).strip()

    if not q_clean:
        return {"matches": [], "page_width": 0, "page_height": 0}

    data = get_file(source["file_path"])
    doc = fitz.open(stream=data, filetype="pdf")

    matches = []
    page_width = 0.0
    page_height = 0.0

    for page_num in range(doc.page_count):
        pg = doc[page_num]
        if page_width == 0:
            page_width = pg.rect.width
            page_height = pg.rect.height

        found = pg.search_for(q_clean, flags=fitz.TEXT_DEHYPHENATE)
        if not found:
            continue

        # Group rects that belong to the same multi-line match occurrence.
        # pymupdf returns one rect per matched line — consecutive rects
        # within 1.5x line height belong to the same match.
        sorted_found = sorted(found, key=lambda r: (r.y0, r.x0))
        groups: list[list] = [[sorted_found[0]]]
        for rect in sorted_found[1:]:
            prev = groups[-1][-1]
            line_h = max(prev.height, rect.height, 10)
            if rect.y0 - prev.y1 < line_h * 1.5:
                groups[-1].append(rect)
            else:
                groups.append([rect])

        for group in groups:
            matches.append({
                "page": page_num + 1,
                "rects": [{"x0": r.x0, "y0": r.y0, "x1": r.x1, "y1": r.y1} for r in group],
            })

    doc.close()
    return {"matches": matches, "page_width": page_width, "page_height": page_height}


@router.get("/ki-assistent/modules/{module_uuid}/sources/{source_uuid}/markdown")
async def convert_source_to_markdown(
    module_uuid: str,
    source_uuid: str,
    force: bool = False,
    current_user: dict = Depends(get_current_user),
):
    """Convert a PDF source to Markdown via KISSKI Docling API.

    Before sending to Docling the PDF is pre-processed with PyMuPDF: any invisible
    OCR text layer that lies on top of rasterised image blocks is redacted so that
    Docling never sees it.  Images from the Docling response are saved to storage
    and referenced as proper URLs in the returned Markdown.
    """
    import httpx
    from src.config import Settings

    user_id = current_user["user_id"]
    module = db.get_kia_module(module_uuid)
    if not module:
        raise HTTPException(status_code=404, detail="Modul nicht gefunden")

    is_owner = module["user_id"] == user_id
    is_enrolled = db.is_student_enrolled(module["id"], user_id)
    if not is_owner and not is_enrolled:
        raise HTTPException(status_code=403, detail="Kein Zugriff")

    source = db.get_kia_source(source_uuid)
    if not source:
        raise HTTPException(status_code=404, detail="Source nicht gefunden")

    ext = Path(source["filename"]).suffix.lower()
    if ext != ".pdf":
        raise HTTPException(status_code=400, detail="Nur für PDF-Dateien verfügbar")

    md_path = str(Path(source["file_path"]).with_suffix(".md"))

    if not force and file_exists(md_path):
        cached = get_file(md_path).decode("utf-8")
        return {"markdown": cached}

    data = get_file(source["file_path"])

    # Strip OCR text layers that lie inside image regions before sending to Docling
    clean_pdf = _strip_image_text_layer(data)

    s = Settings()
    if not s.kisski_api_key:
        raise HTTPException(status_code=500, detail="KISSKI API Key nicht konfiguriert")

    base_url = s.kisski_base_url.rstrip("/")
    convert_url = f"{base_url}/documents/convert?do_ocr=false&extract_tables_as_images=false"

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                convert_url,
                headers={"Authorization": f"Bearer {s.kisski_api_key}", "accept": "application/json"},
                files={"document": (source["filename"], clean_pdf, "application/pdf")},
            )
        response.raise_for_status()
        result = response.json()
    except httpx.HTTPStatusError as e:
        logger.warning("KISSKI Docling API Fehler {}: {} — Fallback auf PyMuPDF", e.response.status_code, e.response.text)
        return _markdown_fallback(data)
    except Exception as e:
        logger.warning("KISSKI Docling API nicht erreichbar: {} — Fallback auf PyMuPDF", e)
        return _markdown_fallback(data)

    markdown: str = result.get("markdown", "")

    if USE_S3:
        from src.storage import _s3, _S3_BUCKET  # type: ignore[attr-defined]
        _s3().put_object(Bucket=_S3_BUCKET, Key=md_path, Body=markdown.encode("utf-8"))
    else:
        Path(md_path).write_text(markdown, encoding="utf-8")

    return {"markdown": markdown}
