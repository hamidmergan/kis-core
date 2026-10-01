import asyncio
import io
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, Response, UploadFile
from loguru import logger

from src import database as db
from src.dependencies import get_current_user, is_admin_user
from src.i18n import get_locale, t
from src.services import feature_provider_choices
from src.storage import get_job_file, load_result_meta, save_queue_file
from src.limits import MAX_IMAGE_BYTES
from src.utils.file_validation import validate_or_raise
from src.quotas import enforce_quota
from src.security.rate_limit import enforce_tool_burst
from src.services.open_jobs import create_counted_job, enforce_open_jobs
from src.dependencies_rbac import require_tool_access
from src.features.bild import optionen

router = APIRouter(
    tags=["image"],
    dependencies=[Depends(require_tool_access("image"))],
)
ALLOWED_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}

# Tool tab -> feature id for the per-tab provider picker.
_TAB_FEATURE = {"generate": "image_gen", "edit": "image_edit", "analyze": "vision"}
# Each variant is a job of its own, so limits, quota and the history treat it like any other.
_MAX_VARIANTEN = {"generate": 4, "edit": 2}
# Jobs that keep the picture they started from.
_MIT_VORLAGE = {"image_edit", "image_analyze"}


def _gueltig(wert, locale: str):
    """Runs an option lookup and turns an unknown value into a 400."""
    try:
        return wert()
    except ValueError:
        raise HTTPException(status_code=400, detail=t("image.invalidOption", locale)) from None


def _varianten(anzahl: int, tab: str, locale: str) -> int:
    if not 1 <= anzahl <= _MAX_VARIANTEN[tab]:
        raise HTTPException(status_code=400, detail=t("image.invalidOption", locale))
    return anzahl


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


@router.post("/image/enhance-prompt")
def enhance_prompt(
    prompt: str = Form(...),
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """A detailed English prompt from a short idea, shown to the person before anything is generated."""
    if not prompt.strip():
        raise HTTPException(status_code=400, detail=t("prompt.empty", locale))
    enforce_tool_burst(current_user.get("user_id", 0), "image_enhance", locale)
    from src.features.bild import beschreibung
    try:
        text = beschreibung.ausformulieren(prompt[:1000])
    except Exception as e:  # noqa: BLE001 - the provider is the only thing that can fail here
        logger.warning("Bild: Beschreibung ausformulieren gescheitert: {}", e)
        raise HTTPException(status_code=502, detail=t("image.enhanceFailed", locale)) from e
    if not text:
        raise HTTPException(status_code=502, detail=t("image.enhanceFailed", locale))
    return {"prompt": text}


@router.post("/image/generate")
def generate_image(
    prompt: str = Form(...),
    format_: str = Form("1:1", alias="format"),
    groesse: str = Form("mittel"),
    qualitaet: str = Form("standard"),
    stil: str = Form("keiner"),
    varianten: int = Form(1),
    ohne_schrift: bool = Form(True),
    prompt_modell: str = Form(""),
    provider_id: int | None = Form(None),
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    if not prompt.strip():
        raise HTTPException(status_code=400, detail=t("prompt.empty", locale))
    size = _gueltig(lambda: optionen.pixel(format_, groesse), locale)
    steps = _gueltig(lambda: optionen.schritte(qualitaet), locale)
    # An expanded description replaces the short one on its way to the model, the job keeps the short name.
    text = _gueltig(lambda: optionen.bild_prompt(prompt_modell.strip() or prompt, stil, ohne_schrift=ohne_schrift),
                    locale)
    anzahl = _varianten(varianten, "generate", locale)
    _validate_provider("image_gen", provider_id, locale)

    user_id = current_user.get("user_id", 0)
    enforce_open_jobs(user_id, locale, "image_generate")
    enforce_tool_burst(user_id, "image_generate", locale)

    from src.tasks.general_tasks import run_image_generate
    job_uuids: list[str] = []
    teilweise = False
    for _ in range(anzahl):
        try:
            enforce_quota(user_id, "image_generate", is_admin_user(current_user), locale)
            job_uuid = uuid.uuid4().hex
            create_counted_job(job_uuid, user_id, "image_generate", prompt[:100], locale=locale)
        except HTTPException:
            # Variants already started stay, the person sees them instead of an error without pictures.
            if not job_uuids:
                raise
            teilweise = True
            break
        task = run_image_generate.delay(job_uuid, text, size, provider_id, steps=steps, titel=prompt,
                                        angaben={"stil": stil, "format": format_, "qualitaet": qualitaet})
        db.set_job_celery_task_id(job_uuid, task.id)
        job_uuids.append(job_uuid)

    logger.info("Image generate jobs {} queued ({}, {})", job_uuids, size, qualitaet)
    return {"job_uuid": job_uuids[0], "job_uuids": job_uuids, "teilweise": teilweise, "status": "pending"}


@router.post("/image/edit")
async def edit_image(
    image: UploadFile = File(...),
    prompt: str = Form(...),
    format_: str = Form("vorlage", alias="format"),
    groesse: str = Form("mittel"),
    qualitaet: str = Form("standard"),
    varianten: int = Form(1),
    provider_id: int | None = Form(None),
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    if not prompt.strip():
        raise HTTPException(status_code=400, detail=t("prompt.empty", locale))
    if not image.filename:
        raise HTTPException(status_code=400, detail=t("file.nameMissing", locale))
    steps = _gueltig(lambda: optionen.schritte(qualitaet, bearbeiten=True), locale)
    if format_ != "vorlage":
        size = _gueltig(lambda: optionen.pixel(format_, groesse), locale)
    anzahl = _varianten(varianten, "edit", locale)
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
    from PIL import Image as PILImage
    with PILImage.open(io.BytesIO(content)) as vorlage:
        breite, hoehe = vorlage.width, vorlage.height
    # A very wide or tall source goes onto a 4:1 canvas, the provider refuses extreme ones.
    breite, hoehe, zuschnitt = optionen.ausgleichen(breite, hoehe)
    if zuschnitt:
        content, ext = optionen.auffuellen(content, breite, hoehe), ".png"
    if format_ == "vorlage":
        # The source keeps its aspect ratio, a portrait was stretched to a square before.
        size = _gueltig(lambda: optionen.wie_vorlage(breite, hoehe, groesse), locale)
    else:
        # A fixed format is what the person asked for, nothing is cut back.
        zuschnitt = None

    user_id = current_user.get("user_id", 0)
    enforce_open_jobs(user_id, locale, "image_edit")
    enforce_tool_burst(user_id, "image_edit", locale)

    from src.tasks.general_tasks import run_image_edit
    display_name = f"{image.filename}: {prompt[:80]}"
    job_uuids: list[str] = []
    teilweise = False
    for _ in range(anzahl):
        try:
            enforce_quota(user_id, "image_edit", is_admin_user(current_user), locale)
            job_uuid = uuid.uuid4().hex
            create_counted_job(job_uuid, user_id, "image_edit", display_name, locale=locale)
        except HTTPException:
            if not job_uuids:
                raise
            teilweise = True
            break
        # Every job deletes its source at the end, so each one gets its own copy.
        input_path = await asyncio.to_thread(save_queue_file, user_id, job_uuid, ext, content)
        db.set_job_input_path(job_uuid, input_path)
        task = run_image_edit.delay(job_uuid, input_path, image.filename, prompt, provider_id, size=size, steps=steps,
                                    zuschnitt=zuschnitt, angaben={"format": format_, "qualitaet": qualitaet})
        db.set_job_celery_task_id(job_uuid, task.id)
        job_uuids.append(job_uuid)

    logger.info("Image edit jobs {} queued for '{}' ({})", job_uuids, image.filename, size)
    return {"job_uuid": job_uuids[0], "job_uuids": job_uuids, "teilweise": teilweise, "status": "pending"}


@router.get("/image/{job_uuid}/vorlage")
def edit_source(
    job_uuid: str,
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """The picture a job started from: the source of an edit, or the picture a description was about."""
    job = db.get_job(job_uuid)
    # Owner only, a foreign job_uuid must not show another person's picture.
    if not job or job["user_id"] != current_user.get("user_id", 0) or job["tool"] not in _MIT_VORLAGE:
        raise HTTPException(status_code=404, detail=t("job.notFound", locale))
    name = (load_result_meta(job["user_id"], job_uuid) or {}).get("vorlage")
    if not name:
        raise HTTPException(status_code=404, detail=t("job.noDownloadAvailable", locale))
    try:
        daten = get_job_file(job["user_id"], job_uuid, name)
    except Exception:
        raise HTTPException(status_code=404, detail=t("job.fileExpired", locale)) from None
    return Response(content=daten, media_type="image/png" if name.endswith(".png") else "image/jpeg")


@router.post("/image/analyze")
async def analyze_image(
    image: UploadFile = File(...),
    prompt: str = Form(""),
    aufgabe: str = Form(""),
    sprache: str = Form(""),
    provider_id: int | None = Form(None),
    quelle: str = Form(""),
    titel: str = Form(""),
    current_user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    if not image.filename:
        raise HTTPException(status_code=400, detail=t("file.nameMissing", locale))
    # Without a task an older page sends only the text field, a question then, or a description without one.
    aufgabe = aufgabe or ("frage" if prompt.strip() else "beschreiben")
    if aufgabe == "frage" and not prompt.strip():
        raise HTTPException(status_code=400, detail=t("image.questionMissing", locale))
    anweisung = _gueltig(lambda: optionen.analyse_anweisung(aufgabe, sprache or locale, prompt), locale)
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
    # The picture the answer belongs to, only an own picture job counts, otherwise the answer stands alone.
    quelle_job = db.get_job(quelle) if quelle else None
    if not quelle_job or quelle_job["user_id"] != user_id or not quelle_job["tool"].startswith("image_"):
        quelle = ""
    enforce_open_jobs(user_id, locale, "image_analyze")
    enforce_tool_burst(user_id, "image_analyze", locale)
    enforce_quota(user_id, "image_analyze", is_admin_user(current_user), locale)

    display_name = f"{image.filename}: {prompt[:80]}" if prompt.strip() else image.filename
    create_counted_job(job_uuid, user_id, "image_analyze", display_name, locale=locale)
    input_path = await asyncio.to_thread(save_queue_file, user_id, job_uuid, ext, content)
    db.set_job_input_path(job_uuid, input_path)

    from src.tasks.general_tasks import run_image_analyze
    task = run_image_analyze.delay(job_uuid, input_path, image.filename, prompt, provider_id, anweisung=anweisung,
                                   angaben={"quelle": quelle, "titel": titel.strip()[:200]})
    db.set_job_celery_task_id(job_uuid, task.id)

    logger.info("Image analyze job {} queued for '{}'", job_uuid, image.filename)
    return {"job_uuid": job_uuid, "status": "pending"}
