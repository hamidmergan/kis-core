"""Settings-Endpoints: Provider-Ping, Settings-Lesen, Settings-Update."""

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
    check_thorsten_available,
    dns_ok,
)

from src.routes.admin._embedding import invalidate_fingerprint_cache
from src.routes.admin._models import UpdateSettingsRequest

router = APIRouter(tags=["admin"])


@router.get("/settings/ping")
async def ping_service(service: str, _admin=Depends(get_admin_user)):
    """On-demand reachability probe. Called from the UI when the user clicks
    a 'Testen' button, so the main settings load stays instant.
    """
    from src.dependencies import get_settings as _get_settings
    app_settings = _get_settings()

    checks = {
        "fish_speech": check_fish_speech_available,
        "kokoro": check_kokoro_available,
        "mylab_tts": check_mylab_available,
        "thorsten": check_thorsten_available,
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
        "thorsten": app_settings.thorsten_base_url,
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
    thorsten_available = None
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
        "thorsten_enabled": _enabled("thorsten_enabled"),
        "thorsten_configured": bool(app_settings.thorsten_base_url),
        "thorsten_available": thorsten_available,
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
        "ollama_embedding_enabled": _enabled("ollama_embedding_enabled", "false"),
        "ollama_embedding_configured": ollama_configured,
        # ── Bild-Generierung ──
        "kisski_image_gen_enabled": _enabled("kisski_image_gen_enabled"),
        "kisski_image_gen_configured": kisski_configured,
        "mylab_image_gen_enabled": _enabled("mylab_image_gen_enabled"),
        "mylab_image_gen_configured": mylab_base_configured,
        "mylab_image_gen_available": mylab_base_available,
        # ── Bild-Analyse ── (KISSKI only, keine myLab-Alternative verfuegbar)
        "kisski_image_analyze_enabled": _enabled("kisski_image_analyze_enabled"),
        "kisski_image_analyze_configured": kisski_configured,
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
        "ollama_llm_enabled": _enabled("ollama_llm_enabled", "false"),
        "ollama_llm_configured": ollama_configured,
        # ── Transkript-Übersetzung (EN) ──
        "transcript_translation_provider": db.get_setting("transcript_translation_provider", "llm"),
    }


# Simple bool-Setting-Keys: werden alle nach dem gleichen Schema gesetzt
_SIMPLE_BOOL_FIELDS = (
    "whitelist_enabled",
    "elevenlabs_enabled", "fish_speech_enabled", "kokoro_enabled", "mylab_enabled", "thorsten_enabled",
    "kisski_whisper_enabled", "mylab_whisper_enabled",
    "kisski_image_gen_enabled", "mylab_image_gen_enabled",
    "kisski_image_analyze_enabled",
    "kisski_image_edit_enabled", "mylab_image_edit_enabled",
    "kisski_ocr_enabled", "mylab_ocr_enabled",
    "kisski_llm_enabled", "mylab_llm_enabled", "ollama_llm_enabled",
)

_EMBEDDING_KEYS = ("kisski_embedding_enabled", "mylab_embedding_enabled", "ollama_embedding_enabled")


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
    embedding_changed = False
    for active_key in _EMBEDDING_KEYS:
        requested = body_dict.get(active_key)
        if requested is None:
            continue
        if requested:
            # Enable this one, disable all others
            db.set_setting(active_key, "true")
            for other in _EMBEDDING_KEYS:
                if other != active_key:
                    db.set_setting(other, "false")
            embedding_changed = True
        else:
            # Refuse to disable the last active provider — exactly one must stay on
            currently_on = [k for k in _EMBEDDING_KEYS if db.get_setting(k, "false").lower() == "true"]
            if currently_on == [active_key]:
                raise HTTPException(
                    status_code=400,
                    detail="Mindestens ein Embedding-Anbieter muss aktiv bleiben. Aktiviere zuerst einen anderen.",
                )
            db.set_setting(active_key, "false")
            embedding_changed = True

    if embedding_changed:
        invalidate_fingerprint_cache()

    # Transkript-Übersetzung: only "deepl" oder "llm"
    if body.transcript_translation_provider is not None:
        if body.transcript_translation_provider not in ("deepl", "llm"):
            raise HTTPException(status_code=400, detail="Ungültiger Übersetzungs-Provider")
        db.set_setting("transcript_translation_provider", body.transcript_translation_provider)

    return {"ok": True}
