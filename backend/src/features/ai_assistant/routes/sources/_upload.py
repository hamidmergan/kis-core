"""Source upload / retry / delete."""
import uuid

from ._shared import (
    Path, APIRouter, Depends, File, HTTPException, UploadFile, logger, db,
    get_current_user, KIA_SOURCE_MAX_PAGES, KIA_WORKSPACE_MAX_SOURCES,
    delete_file, _convert_office_to_pdf, _mp4_faststart, _count_pages,
    _require_own_workspace, _save_source_file,
    _ALLOWED_EXTENSIONS, _MAX_UPLOAD_BYTES,
)

router = APIRouter(tags=["ki-assistent: sources"])


@router.post("/ai-assistant/workspaces/{workspace_uuid}/sources")
async def upload_source(
    workspace_uuid: str,
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    workspace = _require_own_workspace(workspace_uuid, current_user["user_id"])

    existing_sources = db.get_aia_sources_by_workspace(workspace["id"])
    if len(existing_sources) >= KIA_WORKSPACE_MAX_SOURCES:
        raise HTTPException(
            status_code=409,
            detail=f"Maximal {KIA_WORKSPACE_MAX_SOURCES} Sources pro Workspace erlaubt. Bitte lösche nicht mehr benötigte Sources.",
        )

    if not file.filename:
        raise HTTPException(status_code=400, detail="Dateiname fehlt")
    ext = Path(file.filename).suffix.lower()
    if ext not in _ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Nur {', '.join(sorted(_ALLOWED_EXTENSIONS))} erlaubt",
        )

    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Datei ist leer")
    if len(data) > _MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Datei zu groß (max 500 MB)")

    stored_filename = file.filename
    if ext in (".docx", ".pptx"):
        logger.info("KI Tutor: converting {} to PDF ({})", ext, file.filename)
        data = _convert_office_to_pdf(data, ext)
        stored_filename = Path(file.filename).stem + ".pdf"
        ext = ".pdf"
    elif ext == ".mp4":
        logger.info("KI Tutor: applying MP4 faststart ({})", file.filename)
        data = _mp4_faststart(data)

    page_count = _count_pages(ext, data)
    if page_count is not None and page_count > KIA_SOURCE_MAX_PAGES:
        raise HTTPException(
            status_code=413,
            detail=f"Dokument hat {page_count} Seiten — max. {KIA_SOURCE_MAX_PAGES} Seiten erlaubt. Bitte teile das Dokument in kleinere Abschnitte auf.",
        )

    source_uuid = uuid.uuid4().hex
    file_path = _save_source_file(current_user["user_id"], workspace_uuid, source_uuid, ext, data)
    file_type = ext.lstrip(".")

    db.create_aia_source(
        workspace_id=workspace["id"],
        uuid=source_uuid,
        filename=stored_filename,
        file_path=file_path,
        file_type=file_type,
    )

    from src.tasks.aia_tasks import run_index_source
    run_index_source.delay(source_uuid)

    logger.info("KI Tutor: source {} ({}) uploaded to workspace {}", source_uuid, stored_filename, workspace_uuid)
    return {"uuid": source_uuid, "filename": stored_filename, "status": "pending"}


@router.post("/ai-assistant/workspaces/{workspace_uuid}/sources/{source_uuid}/retry")
async def retry_source(
    workspace_uuid: str,
    source_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    _require_own_workspace(workspace_uuid, current_user["user_id"])
    source = db.get_aia_source(source_uuid)
    if not source:
        raise HTTPException(status_code=404, detail="Source nicht gefunden")
    if source["status"] != "failed":
        raise HTTPException(status_code=409, detail="Nur fehlgeschlagene Sources können neu indexiert werden")

    db.delete_aia_chunks_by_source(source["id"])
    db.reset_aia_source_for_retry(source_uuid)

    from src.tasks.aia_tasks import run_index_source
    run_index_source.delay(source_uuid)

    logger.info("KI Tutor: source {} retry dispatched", source_uuid)
    return {"uuid": source_uuid, "status": "pending"}


@router.delete("/ai-assistant/workspaces/{workspace_uuid}/sources/{source_uuid}")
async def delete_source(
    workspace_uuid: str,
    source_uuid: str,
    current_user: dict = Depends(get_current_user),
):
    _require_own_workspace(workspace_uuid, current_user["user_id"])
    source = db.get_aia_source(source_uuid)
    if not source:
        raise HTTPException(status_code=404, detail="Source nicht gefunden")
    try:
        delete_file(source["file_path"])
    except Exception as e:
        logger.warning("KI Tutor: could not delete source file {}: {}", source["file_path"], e)
    db.delete_aia_source(source_uuid)
    logger.info("KI Tutor: source {} deleted", source_uuid)
    return {"deleted": source_uuid}
