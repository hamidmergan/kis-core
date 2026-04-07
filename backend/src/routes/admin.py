"""Admin endpoints — only accessible by the configured ADMIN_EMAIL."""

import json

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger
from pydantic import BaseModel

from src import database as db
from src.tool_prompts import (
    SCRIPT_BATCH_PREVIEW as _PROMPT_SCRIPT_BATCH_PREVIEW,
    SCRIPT_REFINE_DEFAULT as _PROMPT_SCRIPT_REFINE_DEFAULT,
    SUMMARY_DEFAULT as _PROMPT_SUMMARY_DEFAULT,
    IMAGE_ANALYZE_DEFAULT as _PROMPT_IMAGE_ANALYZE_DEFAULT,
    TUTOR_SYSTEM_DIRECT as _PROMPT_TUTOR_SYSTEM_DIRECT,
    TUTOR_SYSTEM_RAG as _PROMPT_TUTOR_SYSTEM_RAG,
    TUTOR_POPUP_ACTIONS as _TUTOR_POPUP_ACTIONS,
    TUTOR_SUMMARY_PAGE_SYSTEM as _PROMPT_TUTOR_SUMMARY_PAGE_SYSTEM,
    TUTOR_SUMMARY_PAGE_USER_SMALL as _PROMPT_TUTOR_SUMMARY_PAGE_USER_SMALL,
    TUTOR_SUMMARY_PAGE_USER_LARGE as _PROMPT_TUTOR_SUMMARY_PAGE_USER_LARGE,
    TUTOR_SUMMARY_PAGE_BATCH_USER as _PROMPT_TUTOR_SUMMARY_PAGE_BATCH_USER,
)
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
    # TTS
    elevenlabs_enabled: bool | None = None
    fish_speech_enabled: bool | None = None
    kokoro_enabled: bool | None = None
    mylab_enabled: bool | None = None
    thorsten_enabled: bool | None = None
    # Transkription
    kisski_whisper_enabled: bool | None = None
    mylab_whisper_enabled: bool | None = None
    # Embeddings
    kisski_embedding_enabled: bool | None = None
    mylab_embedding_enabled: bool | None = None
    # Bild-Generierung
    kisski_image_gen_enabled: bool | None = None
    mylab_image_gen_enabled: bool | None = None
    # Bild-Analyse
    kisski_image_analyze_enabled: bool | None = None
    mylab_image_analyze_enabled: bool | None = None
    # Bild-Bearbeitung
    kisski_image_edit_enabled: bool | None = None
    mylab_image_edit_enabled: bool | None = None
    # OCR
    kisski_ocr_enabled: bool | None = None
    mylab_ocr_enabled: bool | None = None
    # LLM Chat
    kisski_llm_enabled: bool | None = None
    mylab_llm_enabled: bool | None = None


class ToggleToolRequest(BaseModel):
    enabled: bool


class UpdatePromptRequest(BaseModel):
    value: str




_PROMPT_REGISTRY = [
    {
        "key": "prompt_script_batch",
        "label": "Screencast-Skripte (Batch-Modus)",
        "description": "Wird im Auto-Modus für parallele Batch-Verarbeitung genutzt. Enthält strukturelle Trennzeichen (|||) die der Parser erwartet – nicht editierbar.",
        "editable": False,
        "default": _PROMPT_SCRIPT_BATCH_PREVIEW,
    },
    {
        "key": "prompt_script_refine",
        "label": "Screencast-Skripte (Einzelfolie)",
        "description": "Wird in Schritt 5 verwendet wenn der Nutzer das KI-Symbol neben einer Folie klickt.",
        "editable": False,
        "default": _PROMPT_SCRIPT_REFINE_DEFAULT,
    },
    {
        "key": "prompt_summary",
        "label": "Zusammenfassung",
        "description": "Wird vom Zusammenfassungs-Tool verwendet. Platzhalter {format} wird zur Laufzeit durch die gewählte Ausgabeformat-Anweisung ersetzt – nicht entfernen.",
        "editable": False,
        "default": _PROMPT_SUMMARY_DEFAULT,
    },
    {
        "key": "prompt_image_analyze",
        "label": "Bild-Analyse",
        "description": "Anweisung für das Bild-Analyse-Tool (qwen3-vl Modell).",
        "editable": False,
        "default": _PROMPT_IMAGE_ANALYZE_DEFAULT,
    },
    {
        "key": "prompt_tutor_system_direct",
        "label": "KI-Tutor: System-Prompt (Popup-Aktionen)",
        "description": "System-Prompt für Popup-Aktionen (Kürzen, Umformulieren etc.) im KI-Tutor. Wird bei markiertem Text verwendet.",
        "editable": False,
        "default": _PROMPT_TUTOR_SYSTEM_DIRECT,
    },
    {
        "key": "prompt_tutor_system_rag",
        "label": "KI-Tutor: System-Prompt (Chat / RAG)",
        "description": "System-Prompt für den KI-Tutor-Chat mit Quellensuche (RAG). Steuert Quellenangaben und Halluzinationsverbot.",
        "editable": False,
        "default": _PROMPT_TUTOR_SYSTEM_RAG,
    },
    {
        "key": "prompt_tutor_summary_page_system",
        "label": "KI-Tutor: Seitenzusammenfassung System",
        "description": "System-Prompt für Seitenzusammenfassungen (alle Modelle). Platzhalter {lang}.",
        "editable": False,
        "default": _PROMPT_TUTOR_SUMMARY_PAGE_SYSTEM,
    },
    {
        "key": "prompt_tutor_summary_page_user_small",
        "label": "KI-Tutor: Seitenzusammenfassung User (kleine Modelle)",
        "description": "User-Prompt mit Platzhaltern {lang} und {content}. Enthält /no_think für qwen3.",
        "editable": False,
        "default": _PROMPT_TUTOR_SUMMARY_PAGE_USER_SMALL,
    },
    {
        "key": "prompt_tutor_summary_page_user_large",
        "label": "KI-Tutor: Seitenzusammenfassung User (große Modelle)",
        "description": "User-Prompt für große Modelle. Platzhalter {content}.",
        "editable": False,
        "default": _PROMPT_TUTOR_SUMMARY_PAGE_USER_LARGE,
    },
    {
        "key": "prompt_tutor_summary_page_batch_user",
        "label": "KI-Tutor: Seitenzusammenfassung User (Batch, große Modelle)",
        "description": "User-Prompt für Batch-Verarbeitung (mehrere Seiten pro Request). Platzhalter {n} und {pages}.",
        "editable": False,
        "default": _PROMPT_TUTOR_SUMMARY_PAGE_BATCH_USER,
    },
    *[
        {
            "key": f"prompt_tutor_popup_{action['key']}",
            "label": f"KI-Tutor Popup: {action['label']}",
            "description": f"Prompt fuer die Popup-Aktion '{action['label']}' im KI-Tutor PDF-Viewer.",
            "editable": False,
            "default": action["prompt"],
        }
        for action in _TUTOR_POPUP_ACTIONS
    ],
]


_TOOLS_CONFIG = [
    {"key": "screencast",      "label": "Screencast"},
    {"key": "screencast-demo", "label": "Screencast-Demo"},
    {"key": "translation",   "label": "Dokumentenübersetzung"},
    {"key": "tts",           "label": "Text in Sprache"},
    {"key": "transcription", "label": "Transkription"},
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


def _check_mylab_available(settings) -> bool:
    if not settings.mylab_tts_base_url:
        return False
    try:
        from src.services.mylab_client import MyLabClient
        return MyLabClient(settings.mylab_tts_base_url).is_available()
    except Exception:
        return False


def _check_thorsten_available(settings) -> bool:
    if not settings.thorsten_base_url:
        return False
    try:
        from src.services.thorsten_client import ThorstenClient
        return ThorstenClient(settings.thorsten_base_url).is_available()
    except Exception:
        return False


def _check_mylab_base_available(settings) -> bool:
    """Prüft ob die myLab-Plattform erreichbar ist (für Whisper, Image, Embeddings, OCR)."""
    url = settings.mylab_base_url or settings.mylab_tts_base_url
    if not url:
        return False
    try:
        import httpx
        with httpx.Client(timeout=5.0) as client:
            resp = client.get(f"{url.rstrip('/')}/v1/models")
        return resp.status_code < 500
    except Exception:
        return False


# --- Settings ---

@router.get("/settings")
async def get_settings(_admin=Depends(get_admin_user)):
    from src.dependencies import get_settings as _get_settings
    app_settings = _get_settings()

    kisski_configured = bool(app_settings.kisski_api_key)
    ollama_configured = bool(app_settings.ollama_base_url)
    mylab_base_configured = bool(app_settings.mylab_base_url or app_settings.mylab_tts_base_url)
    mylab_base_available = _check_mylab_base_available(app_settings) if mylab_base_configured else False

    def _enabled(key: str, default: str = "true") -> bool:
        return db.get_setting(key, default).lower() == "true"

    return {
        "whitelist_enabled": _enabled("whitelist_enabled"),
        "demo_data": _enabled("demo_data", "false"),
        # ── TTS ──
        "elevenlabs_enabled": _enabled("elevenlabs_enabled"),
        "elevenlabs_configured": bool(app_settings.elevenlabs_api_key),
        "fish_speech_enabled": _enabled("fish_speech_enabled"),
        "fish_speech_configured": bool(app_settings.fish_speech_base_url),
        "fish_speech_available": _check_fish_speech_available(app_settings),
        "kokoro_enabled": _enabled("kokoro_enabled"),
        "kokoro_configured": bool(app_settings.kokoro_base_url),
        "kokoro_available": _check_kokoro_available(app_settings),
        "mylab_enabled": _enabled("mylab_enabled"),
        "mylab_configured": bool(app_settings.mylab_tts_base_url),
        "mylab_available": _check_mylab_available(app_settings),
        "thorsten_enabled": _enabled("thorsten_enabled"),
        "thorsten_configured": bool(app_settings.thorsten_base_url),
        "thorsten_available": _check_thorsten_available(app_settings),
        # ── Transkription ──
        "kisski_whisper_enabled": _enabled("kisski_whisper_enabled"),
        "kisski_whisper_configured": kisski_configured,
        "mylab_whisper_enabled": _enabled("mylab_whisper_enabled"),
        "mylab_whisper_configured": mylab_base_configured,
        "mylab_whisper_available": mylab_base_available,
        # ── Embeddings ──
        "kisski_embedding_enabled": _enabled("kisski_embedding_enabled"),
        "kisski_embedding_configured": kisski_configured,
        "mylab_embedding_enabled": _enabled("mylab_embedding_enabled"),
        "mylab_embedding_configured": mylab_base_configured,
        "mylab_embedding_available": mylab_base_available,
        # ── Bild-Generierung ──
        "kisski_image_gen_enabled": _enabled("kisski_image_gen_enabled"),
        "kisski_image_gen_configured": kisski_configured,
        "mylab_image_gen_enabled": _enabled("mylab_image_gen_enabled"),
        "mylab_image_gen_configured": mylab_base_configured,
        "mylab_image_gen_available": mylab_base_available,
        # ── Bild-Analyse ──
        "kisski_image_analyze_enabled": _enabled("kisski_image_analyze_enabled"),
        "kisski_image_analyze_configured": kisski_configured,
        "mylab_image_analyze_enabled": _enabled("mylab_image_analyze_enabled"),
        "mylab_image_analyze_configured": mylab_base_configured,
        "mylab_image_analyze_available": mylab_base_available,
        # ── Bild-Bearbeitung ──
        "kisski_image_edit_enabled": _enabled("kisski_image_edit_enabled"),
        "kisski_image_edit_configured": kisski_configured,
        "mylab_image_edit_enabled": _enabled("mylab_image_edit_enabled"),
        "mylab_image_edit_configured": mylab_base_configured,
        "mylab_image_edit_available": mylab_base_available,
        # ── OCR ──
        "kisski_ocr_enabled": _enabled("kisski_ocr_enabled"),
        "kisski_ocr_configured": kisski_configured,
        "mylab_ocr_enabled": _enabled("mylab_ocr_enabled", "false"),
        "mylab_ocr_configured": mylab_base_configured,
        "mylab_ocr_available": mylab_base_available,
        # ── LLM Chat ──
        "kisski_llm_enabled": _enabled("kisski_llm_enabled"),
        "kisski_llm_configured": kisski_configured,
        "mylab_llm_enabled": _enabled("mylab_llm_enabled", "false"),
        "mylab_llm_configured": mylab_base_configured,
        "mylab_llm_available": mylab_base_available,
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
    if body.mylab_enabled is not None:
        db.set_setting("mylab_enabled", "true" if body.mylab_enabled else "false")
    if body.thorsten_enabled is not None:
        db.set_setting("thorsten_enabled", "true" if body.thorsten_enabled else "false")
    # Transkription
    if body.kisski_whisper_enabled is not None:
        db.set_setting("kisski_whisper_enabled", "true" if body.kisski_whisper_enabled else "false")
    if body.mylab_whisper_enabled is not None:
        db.set_setting("mylab_whisper_enabled", "true" if body.mylab_whisper_enabled else "false")
    # Embeddings
    if body.kisski_embedding_enabled is not None:
        db.set_setting("kisski_embedding_enabled", "true" if body.kisski_embedding_enabled else "false")
    if body.mylab_embedding_enabled is not None:
        db.set_setting("mylab_embedding_enabled", "true" if body.mylab_embedding_enabled else "false")
    # Bild-Generierung
    if body.kisski_image_gen_enabled is not None:
        db.set_setting("kisski_image_gen_enabled", "true" if body.kisski_image_gen_enabled else "false")
    if body.mylab_image_gen_enabled is not None:
        db.set_setting("mylab_image_gen_enabled", "true" if body.mylab_image_gen_enabled else "false")
    # Bild-Analyse
    if body.kisski_image_analyze_enabled is not None:
        db.set_setting("kisski_image_analyze_enabled", "true" if body.kisski_image_analyze_enabled else "false")
    if body.mylab_image_analyze_enabled is not None:
        db.set_setting("mylab_image_analyze_enabled", "true" if body.mylab_image_analyze_enabled else "false")
    # Bild-Bearbeitung
    if body.kisski_image_edit_enabled is not None:
        db.set_setting("kisski_image_edit_enabled", "true" if body.kisski_image_edit_enabled else "false")
    if body.mylab_image_edit_enabled is not None:
        db.set_setting("mylab_image_edit_enabled", "true" if body.mylab_image_edit_enabled else "false")
    # OCR
    if body.kisski_ocr_enabled is not None:
        db.set_setting("kisski_ocr_enabled", "true" if body.kisski_ocr_enabled else "false")
    if body.mylab_ocr_enabled is not None:
        db.set_setting("mylab_ocr_enabled", "true" if body.mylab_ocr_enabled else "false")
    # LLM Chat
    if body.kisski_llm_enabled is not None:
        db.set_setting("kisski_llm_enabled", "true" if body.kisski_llm_enabled else "false")
    if body.mylab_llm_enabled is not None:
        db.set_setting("mylab_llm_enabled", "true" if body.mylab_llm_enabled else "false")
    return {"ok": True}


# --- Tool visibility ---

_DEFAULT_DISABLED: set[str] = set()


@router.get("/tools")
async def get_tools(_user=Depends(get_current_user)):
    """Return all tools with their enabled/disabled state. Accessible by all logged-in users."""
    disabled = set(json.loads(db.get_setting("disabled_tools", "[]")))
    enabled_overrides = set(json.loads(db.get_setting("enabled_tools_override", "[]")))

    def _is_enabled(key: str) -> bool:
        if key in disabled:
            return False
        if key in _DEFAULT_DISABLED and key not in enabled_overrides:
            return False
        return True

    return {
        "tools": [
            {**t, "enabled": _is_enabled(t["key"])}
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
    enabled_overrides = set(json.loads(db.get_setting("enabled_tools_override", "[]")))
    if body.enabled:
        disabled.discard(tool_key)
        if tool_key in _DEFAULT_DISABLED:
            enabled_overrides.add(tool_key)
    else:
        enabled_overrides.discard(tool_key)
        if tool_key not in _DEFAULT_DISABLED:
            disabled.add(tool_key)
    db.set_setting("disabled_tools", json.dumps(list(disabled)))
    db.set_setting("enabled_tools_override", json.dumps(list(enabled_overrides)))
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


# --- Stats ---

@router.get("/stats")
async def get_stats(
    days: int = Query(default=30, ge=1, le=365),
    _admin=Depends(get_admin_user),
):
    raw = db.get_job_stats(days)

    # Pivot by_tool_status into {tool: {total, success, failed}}
    tools: dict[str, dict] = {}
    for row in raw["by_tool_status"]:
        t = row["tool"]
        if t not in tools:
            tools[t] = {"tool": t, "label": _TOOL_LABELS.get(t, t), "total": 0, "success": 0, "failed": 0}
        tools[t]["total"] += row["cnt"]
        if row["status"] == "success":
            tools[t]["success"] = row["cnt"]
        elif row["status"] == "failed":
            tools[t]["failed"] = row["cnt"]

    # Add avg duration
    for t, info in tools.items():
        info["avg_seconds"] = raw["avg_duration"].get(t)

    # Activity log
    activity = db.get_job_activity_log(days, limit=50)
    for a in activity:
        a["tool_label"] = _TOOL_LABELS.get(a["tool"], a["tool"])

    return {
        "by_tool": sorted(tools.values(), key=lambda x: x["total"], reverse=True),
        "activity": activity,
        "days": days,
    }


# --- Jobs ---

_TOOL_LABELS = {
    "screencast_demo_render": "Demo-Screencast",
    "screencast_render": "Screencast",
    "screencast_translate": "Screencast-Übersetzung",
    "screencast_auto": "Screencast (Auto)",
    "tts": "Text in Sprache",
    "translation": "Übersetzung",
    "transcription": "Transkription",
    "image_generate": "Bild-Generierung",
    "image_edit": "Bild-Bearbeitung",
    "image_analyze": "Bild-Analyse",
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
    """Alle aktiven User mit Kontingenten (auch ohne bisherige Aktivität)."""
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
        if row["quota_type"] is None:
            # User exists but has no quota entries yet — fill from QUOTA_DEFAULTS
            for cfg_type, cfg in QUOTA_DEFAULTS.items():
                effective_limit = cfg["limit"]
                users[uid]["quotas"].append({
                    "quota_type": cfg_type,
                    "label": cfg["label"],
                    "used": 0,
                    "limit": effective_limit,
                    "limit_is_unlimited": effective_limit == -1,
                    "override": None,
                    "reset_at": None,
                })
        else:
            cfg = QUOTA_DEFAULTS.get(row["quota_type"], {})
            effective_limit = row["override"] if row["override"] is not None else cfg.get("limit", 30)
            users[uid]["quotas"].append({
                "quota_type": row["quota_type"],
                "label": cfg.get("label", row["quota_type"]),
                "used": row["used"],
                "limit": effective_limit,
                "limit_is_unlimited": effective_limit == -1,
                "override": row["override"],
                "reset_at": (row["reset_at"].isoformat() + "Z") if row["reset_at"] else None,
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
            "reset_at": (reset_at.isoformat() + "Z") if reset_at else None,
        })
    return {
        "user_id": user_id,
        "quotas": result,
        "global_reset_at": (global_reset_at.isoformat() + "Z") if global_reset_at else None,
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


# ─── KI-Tutor Stats ─────────────────────────────────────────────────────────

_TOOL_LABELS_TUTOR = {
    "lernkarten": "Lernkarten",
    "karteikarten": "Karteikarten",
    "quiz": "Quiz",
    "lueckentext": "Lückentext",
    "vokabeltest": "Vokabeltest",
}

@router.get("/ki-tutor/stats")
async def get_ki_tutor_stats(
    days: int = Query(default=30, ge=1, le=365),
    mode: str | None = Query(default=None, regex="^(quelle|glossar)$"),
    _admin=Depends(get_admin_user),
):
    """Aggregated KI-Tutor statistics for the admin dashboard."""
    return db.get_ki_tutor_admin_stats(days, mode=mode)
