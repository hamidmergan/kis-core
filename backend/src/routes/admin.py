"""Admin endpoints — only accessible by the configured ADMIN_EMAIL."""

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from pydantic import BaseModel

from src import database as db
from src.services.kisski_client import _SYSTEM_PROMPT_EN as _PROMPT_SCRIPT_EN_DEFAULT
from src.celery_app import celery_app
from src.dependencies import get_admin_user, get_current_user
from src.limits import QUOTA_DEFAULTS
from src.storage import delete_job_folder

router = APIRouter(prefix="/admin", tags=["admin"])


class AddWhitelistRequest(BaseModel):
    email: str


class UpdateSettingsRequest(BaseModel):
    whitelist_enabled: bool | None = None
    demo_data: bool | None = None
    elevenlabs_enabled: bool | None = None
    fish_speech_enabled: bool | None = None
    kokoro_enabled: bool | None = None


class ToggleToolRequest(BaseModel):
    enabled: bool


class UpdatePromptRequest(BaseModel):
    value: str



_PROMPT_SCRIPT_BATCH_PREVIEW = (
    "You are an expert at creating spoken narration scripts for presentation slides. "
    "Generate a spoken script for EACH of the {N} slides below (slides {X} to {Y} of {Z} total).\n"
    "Rules:\n"
    "- Do NOT add any new information.\n"
    "- Do NOT hallucinate.\n"
    "- Keep all facts, numbers, names, and dates exactly as they are.\n"
    "- Output MUST be in English.\n"
    "- Convert bullet points, tables, and lists into flowing text.\n"
    "- Remove citations, footnotes, and formatting artifacts.\n"
    "- NO semicolons, NO dashes – use only periods and commas.\n"
    "- Address the audience directly as 'you'.\n"
    "- Natural, conversational tone – like a university lecturer speaking.\n"
    "- Only use a greeting on slide 1 if the content clearly indicates a title slide.\n"
    "- Never use greetings on any other slide.\n"
    "- Keep each script between 20 and 100 words.\n"
    "- For empty slides, output nothing (just write the ||| delimiter).\n"
    "- Do NOT add closing statements like 'thank you' or 'that concludes' on any slide.\n"
    "\n"
    "Separate the {N} scripts using the delimiter ||| on its own line.\n"
    "No other text before, between, or after. Example for 3 slides:\n"
    "Script text for slide one.\n"
    "|||\n"
    "Script text for slide two.\n"
    "|||\n"
    "Script text for slide three.\n"
    "\n"
    "[{N}, {X}, {Y}, {Z} werden zur Laufzeit durch die tatsächliche Batch-Größe ersetzt]"
)


_PROMPT_SUMMARIZE_DEFAULT = (
    "Erstelle eine ausführliche Zusammenfassung des folgenden Transkripts. "
    "Erfasse alle wichtigen Themen, Argumente, Fakten, Zahlen und Schlussfolgerungen vollständig. "
    "Die Zusammenfassung soll strukturiert und gut lesbar sein, aber nichts Wesentliches auslassen. "
    "Antworte nur mit der Zusammenfassung, ohne Einleitung oder Erklärung."
)

_PROMPT_SUMMARY_DEFAULT = (
    "Erstelle eine Zusammenfassung ausschließlich basierend auf dem folgenden Inhalt. "
    "Erfinde nichts, ergänze nichts, interpretiere nichts was nicht explizit im Text steht. "
    "{format} "
    "Antworte nur mit der Zusammenfassung, ohne einleitende oder abschließende Erklärung."
)

_PROMPT_IMAGE_ANALYZE_DEFAULT = (
    "You are an assistant helping university lecturers analyze visual content. "
    "Describe the image in detail: transcribe all visible text verbatim, explain "
    "diagrams, charts, tables, and other visual elements. Be precise and complete. "
    "Respond in the same language as the image content."
)

_PROMPT_REGISTRY = [
    {
        "key": "prompt_script_en",
        "label": "Skript-Erstellung",
        "description": "System-Prompt für das Skript-Tool und den Screencast (Einzelfolie).",
        "editable": True,
        "default": _PROMPT_SCRIPT_EN_DEFAULT,
    },
    {
        "key": "prompt_script_batch",
        "label": "Screencast-Skripte (Batch-Modus)",
        "description": "Wird im Auto-Modus für parallele Batch-Verarbeitung genutzt. Enthält strukturelle Trennzeichen (|||) die der Parser erwartet – nicht editierbar.",
        "editable": False,
        "default": _PROMPT_SCRIPT_BATCH_PREVIEW,
    },
    {
        "key": "prompt_summarize",
        "label": "Transkript-Zusammenfassung",
        "description": "Wird nach der Transkription genutzt um das Transkript zusammenzufassen.",
        "editable": True,
        "default": _PROMPT_SUMMARIZE_DEFAULT,
    },
    {
        "key": "prompt_summary",
        "label": "Zusammenfassung",
        "description": "Wird vom Zusammenfassungs-Tool verwendet. Platzhalter {format} wird zur Laufzeit durch die gewählte Ausgabeformat-Anweisung ersetzt – nicht entfernen.",
        "editable": True,
        "default": _PROMPT_SUMMARY_DEFAULT,
    },
    {
        "key": "prompt_image_analyze",
        "label": "Bild-Analyse",
        "description": "Anweisung für das Bild-Analyse-Tool (qwen3-vl Modell).",
        "editable": True,
        "default": _PROMPT_IMAGE_ANALYZE_DEFAULT,
    },
]


_TOOLS_CONFIG = [
    {"key": "screencast",      "label": "Screencast"},
    {"key": "screencast-demo", "label": "Screencast-Demo"},
    {"key": "translation",   "label": "Dokumentenübersetzung"},
    {"key": "tts",           "label": "Text-to-Speech"},
    {"key": "script",        "label": "Skript erstellen"},
    {"key": "transcription", "label": "Transkription"},
    {"key": "video_dubbing", "label": "Video-Dubbing"},
    {"key": "image",         "label": "Bild-KI"},
    {"key": "glossary",      "label": "Glossare"},
    {"key": "summary",       "label": "Zusammenfassung"},
]



def _check_fish_speech_available(settings) -> bool:
    if not settings.fish_speech_base_url:
        return False
    try:
        from src.services.fish_speech_client import FishSpeechClient
        return FishSpeechClient(settings.fish_speech_base_url).is_available()
    except Exception:
        return False


def _check_kokoro_available(settings) -> bool:
    if not settings.kokoro_base_url:
        return False
    try:
        from src.services.kokoro_client import KokoroClient
        return KokoroClient(settings.kokoro_base_url).is_available()
    except Exception:
        return False


# --- Settings ---

@router.get("/settings")
async def get_settings(_admin=Depends(get_admin_user)):
    from src.dependencies import get_settings as _get_settings
    app_settings = _get_settings()
    return {
        "whitelist_enabled": db.get_setting("whitelist_enabled", "true").lower() == "true",
        "demo_data": db.get_setting("demo_data", "false").lower() == "true",
        "elevenlabs_enabled": db.get_setting("elevenlabs_enabled", "true").lower() == "true",
        "elevenlabs_configured": bool(app_settings.elevenlabs_api_key),
        "fish_speech_enabled": db.get_setting("fish_speech_enabled", "true").lower() == "true",
        "fish_speech_configured": bool(app_settings.fish_speech_base_url),
        "fish_speech_available": _check_fish_speech_available(app_settings),
        "kokoro_enabled": db.get_setting("kokoro_enabled", "true").lower() == "true",
        "kokoro_configured": bool(app_settings.kokoro_base_url),
        "kokoro_available": _check_kokoro_available(app_settings),
    }


@router.patch("/settings")
async def update_settings(body: UpdateSettingsRequest, _admin=Depends(get_admin_user)):
    if body.whitelist_enabled is not None:
        db.set_setting("whitelist_enabled", "true" if body.whitelist_enabled else "false")
    if body.demo_data is not None:
        db.set_setting("demo_data", "true" if body.demo_data else "false")
    if body.elevenlabs_enabled is not None:
        db.set_setting("elevenlabs_enabled", "true" if body.elevenlabs_enabled else "false")
    if body.fish_speech_enabled is not None:
        db.set_setting("fish_speech_enabled", "true" if body.fish_speech_enabled else "false")
    if body.kokoro_enabled is not None:
        db.set_setting("kokoro_enabled", "true" if body.kokoro_enabled else "false")
    return {"ok": True}


# --- Tool visibility ---

@router.get("/tools")
async def get_tools(_user=Depends(get_current_user)):
    """Return all tools with their enabled/disabled state. Accessible by all logged-in users."""
    disabled = set(json.loads(db.get_setting("disabled_tools", "[]")))
    return {
        "tools": [
            {**t, "enabled": t["key"] not in disabled}
            for t in _TOOLS_CONFIG
        ]
    }


@router.patch("/tools/{tool_key}")
async def toggle_tool(tool_key: str, body: ToggleToolRequest, _admin=Depends(get_admin_user)):
    """Enable or disable a tool on the homepage. Admin only."""
    valid_keys = {t["key"] for t in _TOOLS_CONFIG}
    if tool_key not in valid_keys:
        raise HTTPException(status_code=400, detail="Unbekanntes Tool")
    disabled = set(json.loads(db.get_setting("disabled_tools", "[]")))
    if body.enabled:
        disabled.discard(tool_key)
    else:
        disabled.add(tool_key)
    db.set_setting("disabled_tools", json.dumps(list(disabled)))
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


def _tools_matching_query(q: str) -> list[str]:
    q_lower = q.lower()
    return [k for k, label in _TOOL_LABELS.items() if q_lower in label.lower()]


@router.get("/jobs")
async def list_all_jobs(
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    q: str = Query(default=""),
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
    _admin=Depends(get_admin_user),
):
    q = q.strip()
    extra_tools = _tools_matching_query(q) if q else None
    jobs, total = db.get_all_jobs(
        limit=limit, offset=offset, q=q,
        date_from=date_from.strip(), date_to=date_to.strip(),
        extra_tools=extra_tools,
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

    db.delete_job(job_uuid)
    delete_job_folder(job_uuid)

    logger.info("Admin cancelled job: {}", job_uuid)
    return {"ok": True}


# --- System Prompts ---

@router.get("/prompts")
async def get_prompts(_admin=Depends(get_admin_user)):
    result = []
    for p in _PROMPT_REGISTRY:
        current = db.get_setting(p["key"], p["default"]) if p["editable"] else p["default"]
        result.append({
            "key": p["key"],
            "label": p["label"],
            "description": p["description"],
            "editable": p["editable"],
            "current_value": current,
            "default_value": p["default"],
        })
    return {"prompts": result}


@router.patch("/prompts/{key}")
async def update_prompt(key: str, body: UpdatePromptRequest, _admin=Depends(get_admin_user)):
    p = next((x for x in _PROMPT_REGISTRY if x["key"] == key), None)
    if not p:
        raise HTTPException(status_code=404, detail="Prompt nicht gefunden")
    if not p["editable"]:
        raise HTTPException(status_code=400, detail="Dieser Prompt ist schreibgeschützt")
    if not body.value.strip():
        raise HTTPException(status_code=400, detail="Prompt darf nicht leer sein")
    db.set_setting(key, body.value)
    return {"ok": True}


@router.delete("/prompts/{key}/reset")
async def reset_prompt(key: str, _admin=Depends(get_admin_user)):
    p = next((x for x in _PROMPT_REGISTRY if x["key"] == key), None)
    if not p or not p["editable"]:
        raise HTTPException(status_code=400, detail="Nicht erlaubt")
    db.set_setting(key, p["default"])
    return {"ok": True}


# ─── Quota Management ─────────────────────────────────────────────────────────

class SetQuotaOverrideRequest(BaseModel):
    limit_value: int  # -1 = unlimitiert


@router.get("/quota/defaults")
async def get_quota_defaults(_admin=Depends(get_admin_user)):
    """Globale Standard-Limits anzeigen."""
    return {"defaults": QUOTA_DEFAULTS}


@router.get("/quota/overview")
async def get_quota_overview(_admin=Depends(get_admin_user)):
    """Alle User mit Quota-Aktivität (used > 0 oder Override vorhanden)."""
    rows = db.quota_get_all_users_usage()
    # Group by user
    users: dict[int, dict] = {}
    for row in rows:
        uid = row["user_id"]
        if uid not in users:
            users[uid] = {
                "user_id": uid,
                "ldap_username": row["ldap_username"],
                "display_name": row["display_name"],
                "quotas": [],
                "global_reset_at": row.get("global_reset_at"),
            }
        cfg = QUOTA_DEFAULTS.get(row["quota_type"], {})
        effective_limit = row["override"] if row["override"] is not None else cfg.get("limit", 30)
        users[uid]["quotas"].append({
            "quota_type": row["quota_type"],
            "label": cfg.get("label", row["quota_type"]),
            "used": row["used"],
            "limit": effective_limit,
            "limit_is_unlimited": effective_limit == -1,
            "override": row["override"],
            "reset_at": row["reset_at"].isoformat() if row["reset_at"] else None,
        })
    return {"users": list(users.values())}


@router.get("/quota/users/{user_id}")
async def get_user_quota(user_id: int, _admin=Depends(get_admin_user)):
    """Alle Quota-Typen für einen bestimmten User."""
    rows, global_reset_at = db.quota_get_all_for_user(user_id)
    result = []
    for cfg_type, cfg in QUOTA_DEFAULTS.items():
        row = next((r for r in rows if r["quota_type"] == cfg_type), None)
        used = row["used"] if row else 0
        override = row["override"] if row else None
        reset_at = row["reset_at"] if row else None
        effective_limit = override if override is not None else cfg["limit"]
        result.append({
            "quota_type": cfg_type,
            "label": cfg["label"],
            "used": used,
            "limit": effective_limit,
            "limit_is_unlimited": effective_limit == -1,
            "override": override,
            "reset_at": reset_at.isoformat() if reset_at else None,
        })
    return {
        "user_id": user_id,
        "quotas": result,
        "global_reset_at": global_reset_at.isoformat() if global_reset_at else None,
    }


@router.post("/quota/users/{user_id}/{quota_type}/override")
async def set_quota_override(
    user_id: int,
    quota_type: str,
    body: SetQuotaOverrideRequest,
    _admin=Depends(get_admin_user),
):
    """Per-User Limit setzen. -1 = unlimitiert."""
    if quota_type not in QUOTA_DEFAULTS:
        raise HTTPException(status_code=400, detail=f"Unbekannter Quota-Typ: {quota_type}")
    db.quota_set_override(user_id, quota_type, body.limit_value)
    return {"ok": True}


@router.delete("/quota/users/{user_id}/{quota_type}/override")
async def delete_quota_override(
    user_id: int,
    quota_type: str,
    _admin=Depends(get_admin_user),
):
    """Override löschen — User fällt auf globalen Standard zurück."""
    if quota_type not in QUOTA_DEFAULTS:
        raise HTTPException(status_code=400, detail=f"Unbekannter Quota-Typ: {quota_type}")
    db.quota_remove_override(user_id, quota_type)
    return {"ok": True}


@router.post("/quota/users/{user_id}/{quota_type}/reset")
async def reset_user_quota(
    user_id: int,
    quota_type: str,
    _admin=Depends(get_admin_user),
):
    """Quota-Zähler sofort auf 0 setzen und Reset-Timer löschen."""
    if quota_type not in QUOTA_DEFAULTS:
        raise HTTPException(status_code=400, detail=f"Unbekannter Quota-Typ: {quota_type}")
    db.quota_reset(user_id, quota_type)
    return {"ok": True}
