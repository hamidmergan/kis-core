"""Settings endpoints: provider ping, read settings, update settings."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from src import database as db
from src.dependencies import get_admin_user
from src.services.admin.health import (
    check_fish_speech_available,
    check_kokoro_available,
    check_mylab_available,
    check_mylab_base_available,
    dns_ok,
)

from src.routes.admin._embedding import invalidate_fingerprint_cache
from src.routes.admin._models import UpdateSettingsRequest

router = APIRouter(tags=["admin: settings"])


@router.get("/settings/ping")
async def ping_service(service: str, _admin=Depends(get_admin_user)):
    """On-demand reachability probe. Called from the UI when the user clicks
    a 'Testen' (Test) button, so the main settings load stays instant.
    """
    from src.dependencies import get_settings as _get_settings
    app_settings = _get_settings()

    checks = {
        "fish_speech": check_fish_speech_available,
        "kokoro": check_kokoro_available,
        "mylab_tts": check_mylab_available,
        "mylab_base": check_mylab_base_available,
    }
    fn = checks.get(service)
    if fn is None:
        raise HTTPException(status_code=400, detail=f"Unknown service: {service}")

    # URL pick for DNS pre-check
    urls = {
        "fish_speech": app_settings.fish_speech_base_url,
        "kokoro": app_settings.kokoro_base_url,
        "mylab_tts": app_settings.mylab_tts_base_url,
        "mylab_base": app_settings.mylab_base_url or app_settings.mylab_tts_base_url,
    }
    if not await dns_ok(urls[service]):
        return {"service": service, "available": False, "reason": "dns_unreachable"}
    available = await asyncio.to_thread(fn, app_settings)
    return {"service": service, "available": bool(available)}


@router.get("/settings")
async def get_settings(_admin=Depends(get_admin_user)):
    from src.dependencies import get_settings as _get_settings
    app_settings = _get_settings()

    kisski_configured = bool(app_settings.kisski_api_key)
    ollama_configured = bool(app_settings.ollama_base_url)
    mylab_base_configured = bool(app_settings.mylab_base_url or app_settings.mylab_tts_base_url)

    # Reachability is NOT probed here — doing external HTTP calls on every
    # settings load makes the endpoint slow (8s DNS timeout per offline host).
    # The UI uses a separate /admin/settings/ping?service=... endpoint on demand.
    fish_available = None
    kokoro_available = None
    mylab_tts_available = None
    mylab_base_available = None

    def _enabled(key: str, default: str = "true") -> bool:
        return db.get_setting(key, default).lower() == "true"

    return {
        "whitelist_enabled": _enabled("whitelist_enabled"),
        # ── TTS ──
        "elevenlabs_enabled": _enabled("elevenlabs_enabled"),
        "elevenlabs_configured": bool(app_settings.elevenlabs_api_key),
        "fish_speech_enabled": _enabled("fish_speech_enabled"),
        "fish_speech_configured": bool(app_settings.fish_speech_base_url),
        "fish_speech_available": fish_available,
        "kokoro_enabled": _enabled("kokoro_enabled"),
        "kokoro_configured": bool(app_settings.kokoro_base_url),
        "kokoro_available": kokoro_available,
        "mylab_enabled": _enabled("mylab_enabled"),
        "mylab_configured": bool(app_settings.mylab_tts_base_url),
        "mylab_available": mylab_tts_available,
        # ── Transcription ──
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
        "ollama_embedding_enabled": _enabled("ollama_embedding_enabled", "false"),
        "ollama_embedding_configured": ollama_configured,
        # ── Image generation ──
        "kisski_image_gen_enabled": _enabled("kisski_image_gen_enabled"),
        "kisski_image_gen_configured": kisski_configured,
        "mylab_image_gen_enabled": _enabled("mylab_image_gen_enabled"),
        "mylab_image_gen_configured": mylab_base_configured,
        "mylab_image_gen_available": mylab_base_available,
        # ── Image analysis ── (KISSKI only, no myLab alternative available)
        "kisski_image_analyze_enabled": _enabled("kisski_image_analyze_enabled"),
        "kisski_image_analyze_configured": kisski_configured,
        # ── Image editing ──
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
        "ollama_llm_enabled": _enabled("ollama_llm_enabled", "false"),
        "ollama_llm_configured": ollama_configured,
        # ── Transcript translation (EN) ──
        "transcript_translation_provider": db.get_setting("transcript_translation_provider", "llm"),
        "transcript_translation_mode": db.get_setting("transcript_translation_mode", "manual"),
        # ── Provider model names (editable in the admin panel) ──
        "models": _current_models(),
    }


def _current_models() -> dict[str, str]:
    """Read current model names per provider/feature from DB."""
    from src.services.runtime_models import get_model, MODEL_KEYS
    return {key: get_model(key) for key in MODEL_KEYS}


# Simple bool setting keys: all set with the same schema
_SIMPLE_BOOL_FIELDS = (
    "whitelist_enabled",
    "elevenlabs_enabled", "fish_speech_enabled", "kokoro_enabled", "mylab_enabled",
    "kisski_whisper_enabled", "mylab_whisper_enabled",
    "kisski_image_gen_enabled", "mylab_image_gen_enabled",
    "kisski_image_analyze_enabled",
    "kisski_image_edit_enabled", "mylab_image_edit_enabled",
    "kisski_ocr_enabled", "mylab_ocr_enabled",
)

# Radio fields: exactly one provider may be active at a time.
# - Embedding: vector dimension would be inconsistent under parallel operation.
# - LLM: system-wide selection, no fallback (see _resolve_llm_provider).
_EMBEDDING_KEYS = ("kisski_embedding_enabled", "mylab_embedding_enabled", "ollama_embedding_enabled")
_LLM_KEYS = ("kisski_llm_enabled", "mylab_llm_enabled", "ollama_llm_enabled")


def _apply_radio_group(body_dict: dict, keys: tuple[str, ...], group_label: str) -> bool:
    """Enforce 'exactly one active' for a group of mutually-exclusive provider toggles.

    Returns True when any key in the group was changed.
    """
    changed = False
    for active_key in keys:
        requested = body_dict.get(active_key)
        if requested is None:
            continue
        if requested:
            db.set_setting(active_key, "true")
            for other in keys:
                if other != active_key:
                    db.set_setting(other, "false")
            changed = True
        else:
            currently_on = [k for k in keys if db.get_setting(k, "false").lower() == "true"]
            if currently_on == [active_key]:
                raise HTTPException(
                    status_code=400,
                    detail=f"Mindestens ein {group_label}-Anbieter muss aktiv bleiben. Aktiviere zuerst einen anderen.",
                )
            db.set_setting(active_key, "false")
            changed = True
    return changed


@router.patch("/settings")
async def update_settings(body: UpdateSettingsRequest, _admin=Depends(get_admin_user)):
    body_dict = body.model_dump()

    # Simple bool toggles
    for field in _SIMPLE_BOOL_FIELDS:
        val = body_dict.get(field)
        if val is not None:
            db.set_setting(field, "true" if val else "false")

    # Embeddings — exactly one must be enabled at any time.
    # Different embedding models have different vector dimensions, so parallel
    # operation or silent fallback would corrupt the index.
    if _apply_radio_group(body_dict, _EMBEDDING_KEYS, "Embedding"):
        invalidate_fingerprint_cache()

    # LLM Chat - exactly one must be enabled at any time.
    # Provider selection is no longer controlled via env vars (see _resolve_llm_provider).
    _apply_radio_group(body_dict, _LLM_KEYS, "LLM")

    # Transcript translation: only "deepl" or "llm"
    if body.transcript_translation_provider is not None:
        if body.transcript_translation_provider not in ("deepl", "llm"):
            raise HTTPException(status_code=400, detail="Ungültiger Übersetzungs-Provider")
        db.set_setting("transcript_translation_provider", body.transcript_translation_provider)

    # Transcript translation mode: "off" (no EN translation), "auto" (run at ingest),
    # "manual" (default — user triggers via button in transcript panel)
    if body.transcript_translation_mode is not None:
        if body.transcript_translation_mode not in ("off", "auto", "manual"):
            raise HTTPException(status_code=400, detail="Ungültiger Übersetzungs-Modus")
        db.set_setting("transcript_translation_mode", body.transcript_translation_mode)

    # Provider model names
    if body.models:
        from src.services.runtime_models import MODEL_KEYS
        unknown = [k for k in body.models if k not in MODEL_KEYS]
        if unknown:
            raise HTTPException(status_code=400, detail=f"Unbekannte Model-Keys: {unknown}")
        for key, value in body.models.items():
            stripped = (value or "").strip()
            if not stripped:
                raise HTTPException(status_code=400, detail=f"Modellname fuer {key} darf nicht leer sein")
            db.set_setting(key, stripped)
        # Model change for embedding may require reindex
        if any(k in MODEL_KEYS and "embedding" in k for k in body.models):
            invalidate_fingerprint_cache()

    return {"ok": True}
