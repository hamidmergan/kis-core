import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from loguru import logger

from src import database as db
from src.dependencies import get_current_user, is_admin_user
from src.i18n import get_locale, t
from src.services import feature_provider_choices
from src.storage import save_queue_file
from src.limits import MAX_IMAGE_BYTES
from src.utils.file_validation import validate_or_raise
from src.quotas import enforce_quota
from src.security.rate_limit import enforce_tool_burst
from src.services.open_jobs import enforce_open_jobs
from src.dependencies_rbac import require_tool_access

router = APIRouter(
    tags=["image"],
    dependencies=[Depends(require_tool_access("image"))],
)
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}

# Tool tab -> feature id for the per-tab provider picker.
_TAB_FEATURE = {"generate": "image_gen", "edit": "image_edit", "analyze": "vision"}


@router.get("/image/providers/{tab}")
async def list_image_providers(tab: str, _user: dict = Depends(get_current_user)):
    """Reachable providers the admin has registered a model for."""
    feature = _TAB_FEATURE.get(tab)
    if feature is None:
        return {"providers": [], "default_id": None}
    return await feature_provider_choices.list_reachable_choices(feature)


def _validate_provider(feature: str, provider_id: int | None, locale: str) -> None:
    """Rejects a provider the admin has not set up for this feature."""
    if provider_id is not None and not feature_provider_choices.is_eligible(feature, provider_id):
        raise HTTPException(status_code=400, detail=t("image.invalidProvider", locale))


@router.post("/image/generate")
async def generate_image(
    prompt: str = Form(...),
    size: str = Form("1024x1024"),
    provider_id: int | None = Form(None),
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    if not prompt.strip():
        raise HTTPException(status_code=400, detail=t("prompt.empty", locale))
    if size not in {"1024x1024", "1280x720"}:
        raise HTTPException(status_code=400, detail=t("image.invalidSize", locale))
    _validate_provider("image_gen", provider_id, locale)

    job_uuid = uuid.uuid4().hex
    user_id = current_user.get("user_id", 0)
    enforce_open_jobs(user_id, locale)
    enforce_tool_burst(user_id, "image_generate", locale)
    enforce_quota(user_id, "image_generate", is_admin_user(current_user), locale)

    db.create_job(job_uuid, user_id, "image_generate", prompt[:100], locale=locale)

    from src.tasks.general_tasks import run_image_generate
    run_image_generate.delay(job_uuid, prompt, size, provider_id)

    logger.info("Image generate job {} queued", job_uuid)
    return {"job_uuid": job_uuid, "status": "pending"}


@router.post("/image/edit")
async def edit_image(
    image: UploadFile = File(...),
    prompt: str = Form(...),
    provider_id: int | None = Form(None),
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    if not prompt.strip():
        raise HTTPException(status_code=400, detail=t("prompt.empty", locale))
    if not image.filename:
        raise HTTPException(status_code=400, detail=t("file.nameMissing", locale))
    _validate_provider("image_edit", provider_id, locale)

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
    enforce_open_jobs(user_id, locale)
    enforce_tool_burst(user_id, "image_edit", locale)
    enforce_quota(user_id, "image_edit", is_admin_user(current_user), locale)

    display_name = f"{image.filename}: {prompt[:80]}"
    db.create_job(job_uuid, user_id, "image_edit", display_name, locale=locale)
    input_path = save_queue_file(user_id, job_uuid, ext, content)
    db.set_job_input_path(job_uuid, input_path)

    from src.tasks.general_tasks import run_image_edit
    run_image_edit.delay(job_uuid, input_path, image.filename, prompt, provider_id)

    logger.info("Image edit job {} queued for '{}'", job_uuid, image.filename)
    return {"job_uuid": job_uuid, "status": "pending"}


@router.post("/image/analyze")
async def analyze_image(
    image: UploadFile = File(...),
    prompt: str = Form(""),
    provider_id: int | None = Form(None),
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    if not image.filename:
        raise HTTPException(status_code=400, detail=t("file.nameMissing", locale))
    _validate_provider("vision", provider_id, locale)

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
    enforce_open_jobs(user_id, locale)
    enforce_tool_burst(user_id, "image_analyze", locale)
    enforce_quota(user_id, "image_analyze", is_admin_user(current_user), locale)

    display_name = f"{image.filename}: {prompt[:80]}" if prompt.strip() else image.filename
    db.create_job(job_uuid, user_id, "image_analyze", display_name, locale=locale)
    input_path = save_queue_file(user_id, job_uuid, ext, content)
    db.set_job_input_path(job_uuid, input_path)

    from src.tasks.general_tasks import run_image_analyze
    run_image_analyze.delay(job_uuid, input_path, image.filename, prompt, provider_id)

    logger.info("Image analyze job {} queued for '{}'", job_uuid, image.filename)
    return {"job_uuid": job_uuid, "status": "pending"}
