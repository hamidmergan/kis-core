"""Admin endpoints — only accessible by the configured ADMIN_EMAIL."""

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from pydantic import BaseModel

from src import database as db
from src.celery_app import celery_app
from src.dependencies import get_admin_user
from src.storage import delete_file

router = APIRouter(prefix="/admin", tags=["admin"])


class AddWhitelistRequest(BaseModel):
    email: str


class UpdateSettingsRequest(BaseModel):
    whitelist_enabled: bool | None = None
    demo_data: bool | None = None


class SetApiKeyRequest(BaseModel):
    value: str


class SetKisskiBaseUrlRequest(BaseModel):
    value: str


class AddKisskiModelRequest(BaseModel):
    model: str
    is_default: bool = False


# --- Settings ---

@router.get("/settings")
async def get_settings(_admin=Depends(get_admin_user)):
    return {
        "whitelist_enabled": db.get_setting("whitelist_enabled", "true").lower() == "true",
        "demo_data": db.get_setting("demo_data", "false").lower() == "true",
    }


@router.patch("/settings")
async def update_settings(body: UpdateSettingsRequest, _admin=Depends(get_admin_user)):
    if body.whitelist_enabled is not None:
        db.set_setting("whitelist_enabled", "true" if body.whitelist_enabled else "false")
    if body.demo_data is not None:
        db.set_setting("demo_data", "true" if body.demo_data else "false")
    return {"ok": True}


# --- Users ---

@router.get("/users")
async def list_users(
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    q: str = Query(default=""),
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
    _admin=Depends(get_admin_user),
):
    users, total = db.get_all_users(
        limit=limit, offset=offset, q=q.strip(),
        date_from=date_from.strip(), date_to=date_to.strip(),
    )
    return {"users": users, "total": total, "limit": limit, "offset": offset}


@router.get("/users/pending")
async def list_pending_users(_admin=Depends(get_admin_user)):
    return {"users": db.get_pending_users()}


@router.post("/users/{user_id}/approve")
async def approve_user(user_id: int, _admin=Depends(get_admin_user)):
    """Whitelist the user's email and set active=1 so they can log in immediately."""
    row = db.get_user_by_id(user_id)
    if not row:
        raise HTTPException(status_code=404, detail="User nicht gefunden")
    user = dict(row)
    if not user.get("email"):
        raise HTTPException(status_code=400, detail="User hat keine Email-Adresse")
    db.add_to_whitelist(user["email"])
    db.activate_user(user_id)
    return {"ok": True}


# --- Whitelist ---

@router.get("/whitelist")
async def list_whitelist(_admin=Depends(get_admin_user)):
    return {"emails": db.get_whitelist_emails()}


@router.post("/whitelist")
async def add_whitelist(body: AddWhitelistRequest, _admin=Depends(get_admin_user)):
    if not body.email or "@" not in body.email:
        raise HTTPException(status_code=400, detail="Ungültige Email-Adresse")
    db.add_to_whitelist(body.email)
    return {"ok": True}


@router.delete("/whitelist/{email:path}")
async def remove_whitelist(email: str, _admin=Depends(get_admin_user)):
    from src.dependencies import get_settings
    settings = get_settings()
    if email.strip().lower() == settings.admin_email.strip().lower():
        raise HTTPException(status_code=403, detail="Die Admin-Email kann nicht aus der Whitelist entfernt werden.")
    db.remove_from_whitelist(email)
    db.deactivate_user_by_email(email)
    return {"ok": True}


# --- API Config ---

_ALLOWED_KEYS = {"deepl_api_key", "elevenlabs_api_key", "kisski_api_key"}


@router.get("/api-config")
async def get_api_config(_admin=Depends(get_admin_user)):
    return {
        "deepl_api_key": db.get_api_config_masked("deepl_api_key"),
        "elevenlabs_api_key": db.get_api_config_masked("elevenlabs_api_key"),
        "kisski_api_key": db.get_api_config_masked("kisski_api_key"),
        "kisski_base_url": db.get_api_config_value("kisski_base_url"),
        "kisski_models": db.get_kisski_models(),
    }


@router.put("/api-config/keys/{key_name}")
async def set_api_key(key_name: str, body: SetApiKeyRequest, _admin=Depends(get_admin_user)):
    if key_name not in _ALLOWED_KEYS:
        raise HTTPException(status_code=400, detail="Ungültiger Key-Name")
    if not body.value.strip():
        db.delete_api_config(key_name)
    else:
        db.set_api_config(key_name, body.value.strip(), encrypted=True)
    return {"ok": True}


@router.delete("/api-config/keys/{key_name}")
async def delete_api_key(key_name: str, _admin=Depends(get_admin_user)):
    if key_name not in _ALLOWED_KEYS:
        raise HTTPException(status_code=400, detail="Ungültiger Key-Name")
    db.delete_api_config(key_name)
    return {"ok": True}


@router.put("/api-config/kisski-base-url")
async def set_kisski_base_url(body: SetKisskiBaseUrlRequest, _admin=Depends(get_admin_user)):
    db.set_api_config("kisski_base_url", body.value.strip(), encrypted=False)
    return {"ok": True}


@router.post("/api-config/models")
async def add_kisski_model_route(body: AddKisskiModelRequest, _admin=Depends(get_admin_user)):
    if not body.model.strip():
        raise HTTPException(status_code=400, detail="Modellname darf nicht leer sein")
    db.add_kisski_model(body.model.strip(), is_default=body.is_default)
    return {"ok": True}


@router.delete("/api-config/models/{model:path}")
async def remove_kisski_model_route(model: str, _admin=Depends(get_admin_user)):
    db.remove_kisski_model(model)
    return {"ok": True}


@router.patch("/api-config/models/{model:path}/default")
async def set_default_model_route(model: str, _admin=Depends(get_admin_user)):
    db.set_default_kisski_model(model)
    return {"ok": True}


# --- Jobs ---

_TOOL_LABELS = {
    "screencast_demo_render": "Demo-Screencast",
    "screencast_render": "Screencast",
    "screencast_translate": "Screencast-Übersetzung",
    "screencast_auto": "Screencast (Auto)",
    "tts": "Text-to-Speech",
    "video_dubbing": "Video-Dubbing",
    "translation": "Übersetzung",
    "transcription": "Transkription",
    "image_generate": "Bild-Generierung",
    "image_edit": "Bild-Bearbeitung",
    "image_analyze": "Bild-Analyse",
    "script": "Skript-Erstellung",
    "summary": "Zusammenfassung",
}


@router.get("/jobs")
async def list_all_jobs(
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    q: str = Query(default=""),
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
    _admin=Depends(get_admin_user),
):
    jobs, total = db.get_all_jobs(
        limit=limit, offset=offset, q=q.strip(),
        date_from=date_from.strip(), date_to=date_to.strip(),
    )
    result = []
    for j in jobs:
        result.append({
            "job_uuid": j["job_uuid"],
            "tool": j["tool"],
            "tool_label": _TOOL_LABELS.get(j["tool"], j["tool"]),
            "original_filename": j["original_filename"],
            "status": j["status"],
            "error": j["error_message"],
            "created_at": j["created_at"],
            "completed_at": j["completed_at"],
            "user_display_name": j.get("user_display_name") or j.get("ldap_username") or "Unbekannt",
        })
    return {"jobs": result, "total": total, "limit": limit, "offset": offset}


@router.delete("/jobs/{job_uuid}")
async def admin_cancel_job(job_uuid: str, _admin=Depends(get_admin_user)):
    """Admin: cancel and delete any job regardless of owner."""
    job = db.get_job(job_uuid)
    if not job:
        raise HTTPException(status_code=404, detail="Job nicht gefunden")

    if job["celery_task_id"]:
        try:
            celery_app.control.revoke(job["celery_task_id"], terminate=True, reply=False)
        except Exception as e:
            logger.warning("Could not revoke Celery task {}: {}", job["celery_task_id"], e)

    deleted = db.delete_job(job_uuid)
    if deleted:
        for path in (deleted.get("input_path"), deleted.get("result_path")):
            if path:
                delete_file(path)

    logger.info("Admin cancelled job: {}", job_uuid)
    return {"ok": True}
