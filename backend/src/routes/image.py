import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from loguru import logger

from src import database as db
from src.dependencies import get_current_user, is_admin_user
from src.i18n import get_locale, t
from src.storage import save_queue_file
from src.limits import MAX_IMAGE_BYTES
from src.utils.file_validation import validate_or_raise
from src.quotas import enforce_quota
from src.security.rate_limit import enforce_tool_burst
from src.dependencies_rbac import require_tool_access

router = APIRouter(
    tags=["image"],
    dependencies=[Depends(require_tool_access("image"))],
)
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}


@router.post("/image/generate")
async def generate_image(
    prompt: str = Form(...),
    size: str = Form("1024x1024"),
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    if not prompt.strip():
        raise HTTPException(status_code=400, detail=t("prompt.empty", locale))
    if size not in {"1024x1024", "1280x720"}:
        raise HTTPException(status_code=400, detail=t("image.invalidSize", locale))

    job_uuid = uuid.uuid4().hex
    user_id = current_user.get("user_id", 0)
    enforce_tool_burst(user_id, "image_generate", locale)
    enforce_quota(user_id, "image_generate", is_admin_user(current_user), locale)

    db.create_job(job_uuid, user_id, "image_generate", prompt[:100], locale=locale)

    from src.tasks.general_tasks import run_image_generate
    run_image_generate.delay(job_uuid, prompt, size)

    logger.info("Image generate job {} queued", job_uuid)
    return {"job_uuid": job_uuid, "status": "pending"}


@router.post("/image/edit")
async def edit_image(
    image: UploadFile = File(...),
    prompt: str = Form(...),
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    if not prompt.strip():
        raise HTTPException(status_code=400, detail=t("prompt.empty", locale))
    if not image.filename:
        raise HTTPException(status_code=400, detail=t("file.nameMissing", locale))

    ext = Path(image.filename).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail=t("file.onlyPngJpg", locale))

    content = await image.read()
    if not content:
        raise HTTPException(status_code=400, detail=t("image.empty", locale))
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail=t("image.tooLarge", locale))
    validate_or_raise(content, ext, locale)

    job_uuid = uuid.uuid4().hex
    user_id = current_user.get("user_id", 0)
    enforce_tool_burst(user_id, "image_edit", locale)
    enforce_quota(user_id, "image_edit", is_admin_user(current_user), locale)

    display_name = f"{image.filename}: {prompt[:80]}"
    db.create_job(job_uuid, user_id, "image_edit", display_name, locale=locale)
    input_path = save_queue_file(user_id, job_uuid, ext, content)
    db.set_job_input_path(job_uuid, input_path)

    from src.tasks.general_tasks import run_image_edit
    run_image_edit.delay(job_uuid, input_path, image.filename, prompt)

    logger.info("Image edit job {} queued for '{}'", job_uuid, image.filename)
    return {"job_uuid": job_uuid, "status": "pending"}


@router.post("/image/analyze")
async def analyze_image(
    image: UploadFile = File(...),
    prompt: str = Form(""),
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    if not image.filename:
        raise HTTPException(status_code=400, detail=t("file.nameMissing", locale))

    ext = Path(image.filename).suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail=t("file.onlyPngJpg", locale))

    content = await image.read()
    if not content:
        raise HTTPException(status_code=400, detail=t("image.empty", locale))
    if len(content) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail=t("image.tooLarge", locale))
    validate_or_raise(content, ext, locale)

    job_uuid = uuid.uuid4().hex
    user_id = current_user.get("user_id", 0)
    enforce_tool_burst(user_id, "image_analyze", locale)
    enforce_quota(user_id, "image_analyze", is_admin_user(current_user), locale)

    display_name = f"{image.filename}: {prompt[:80]}" if prompt.strip() else image.filename
    db.create_job(job_uuid, user_id, "image_analyze", display_name, locale=locale)
    input_path = save_queue_file(user_id, job_uuid, ext, content)
    db.set_job_input_path(job_uuid, input_path)

    from src.tasks.general_tasks import run_image_analyze
    run_image_analyze.delay(job_uuid, input_path, image.filename, prompt)

    logger.info("Image analyze job {} queued for '{}'", job_uuid, image.filename)
    return {"job_uuid": job_uuid, "status": "pending"}
