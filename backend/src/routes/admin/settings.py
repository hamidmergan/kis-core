"""Settings endpoints: provider ping, read settings, update settings."""

import asyncio

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from src import database as db
from src.dependencies import get_admin_user
from src.i18n import get_locale, t
from src.services.admin.health import (
    check_kokoro_available,
    check_mylab_available,
    check_mylab_base_available,
    dns_ok,
)

from src.routes.admin._embedding import invalidate_fingerprint_cache
from src.routes.admin._models import UpdateSettingsRequest

router = APIRouter(tags=["admin: settings"])


@router.get("/settings/ping")
async def ping_service(
    service: str,
    _admin=Depends(get_admin_user),
    locale: str = Depends(get_locale),
):
    """On-demand reachability probe. Called from the UI when the user clicks
    a 'Testen' (Test) button, so the main settings load stays instant.
    """
    from src.dependencies import get_settings as _get_settings
    app_settings = _get_settings()

    checks = {
        "kokoro": check_kokoro_available,
        "mylab_tts": check_mylab_available,
        "mylab_base": check_mylab_base_available,
    }
    fn = checks.get(service)
    if fn is None:
        raise HTTPException(
            status_code=400,
            detail=t("admin.settings.unknownPingService", locale, service=service),
        )

    # URL pick for DNS pre-check
    urls = {
        "kokoro": app_settings.kokoro_base_url,
        "mylab_tts": app_settings.mylab_tts_base_url,
        "mylab_base": app_settings.fallback_provider_base_url or app_settings.mylab_tts_base_url,
    }
    if not await dns_ok(urls[service]):
        return {"service": service, "available": False, "reason": "dns_unreachable"}
    available = await asyncio.to_thread(fn, app_settings)
    return {"service": service, "available": bool(available)}


@router.get("/settings")
async def get_settings(_admin=Depends(get_admin_user)):
    from src.dependencies import get_settings as _get_settings
    app_settings = _get_settings()

    primary_configured = bool(app_settings.primary_provider_api_key)
    local_configured = bool(app_settings.local_provider_base_url)
    fallback_configured = bool(app_settings.fallback_provider_base_url or app_settings.mylab_tts_base_url)

    # Reachability is NOT probed here - doing external HTTP calls on every
    # settings load makes the endpoint slow (8s DNS timeout per offline host).
    # The UI uses a separate /admin/settings/ping?service=... endpoint on demand.
    kokoro_available = None
    mylab_tts_available = None
    fallback_available = None

    def _enabled(key: str, default: str = "true") -> bool:
        return db.get_setting(key, default).lower() == "true"

    def _last6(s: str) -> str | None:
        return s[-6:] if s and len(s) > 6 else (s or None)

    deepl_override = db.get_setting("deepl_api_key_override", "").strip()
    env_deepl = app_settings.deepl_api_key or ""

    return {
        "whitelist_enabled": _enabled("whitelist_enabled"),
        # ── TTS (flat list of products, not a primary/fallback/local hierarchy) ──
        "elevenlabs_enabled": _enabled("elevenlabs_enabled"),
        "elevenlabs_configured": bool(app_settings.elevenlabs_api_key),
        "kokoro_enabled": _enabled("kokoro_enabled"),
        "kokoro_configured": bool(app_settings.kokoro_base_url),
        "kokoro_available": kokoro_available,
        "mylab_enabled": _enabled("mylab_enabled"),
        "mylab_configured": bool(app_settings.mylab_tts_base_url),
        "mylab_available": mylab_tts_available,
        # ── Transcription ──
        "primary_whisper_enabled": _enabled("primary_whisper_enabled"),
        "primary_whisper_configured": primary_configured,
        "fallback_whisper_enabled": _enabled("fallback_whisper_enabled"),
        "fallback_whisper_configured": fallback_configured,
        "fallback_whisper_available": fallback_available,
        # ── Embeddings ──
        "primary_embedding_enabled": _enabled("primary_embedding_enabled"),
        "primary_embedding_configured": primary_configured,
        "fallback_embedding_enabled": _enabled("fallback_embedding_enabled"),
        "fallback_embedding_configured": fallback_configured,
        "fallback_embedding_available": fallback_available,
        "local_embedding_enabled": _enabled("local_embedding_enabled", "false"),
        "local_embedding_configured": local_configured,
        # ── Image generation ──
        "primary_image_gen_enabled": _enabled("primary_image_gen_enabled"),
        "primary_image_gen_configured": primary_configured,
        "fallback_image_gen_enabled": _enabled("fallback_image_gen_enabled"),
        "fallback_image_gen_configured": fallback_configured,
        "fallback_image_gen_available": fallback_available,
        # ── Image analysis ──
        "primary_image_analyze_enabled": _enabled("primary_image_analyze_enabled"),
        "primary_image_analyze_configured": primary_configured,
        "fallback_image_analyze_enabled": _enabled("fallback_image_analyze_enabled", "false"),
        "fallback_image_analyze_configured": fallback_configured,
        "fallback_image_analyze_available": fallback_available,
        # ── Image editing ──
        "primary_image_edit_enabled": _enabled("primary_image_edit_enabled"),
        "primary_image_edit_configured": primary_configured,
        "fallback_image_edit_enabled": _enabled("fallback_image_edit_enabled"),
        "fallback_image_edit_configured": fallback_configured,
        "fallback_image_edit_available": fallback_available,
        # ── OCR ──
        "ocr_enabled": _enabled("ocr_enabled"),
        "docling_ocr_enabled": _enabled("docling_ocr_enabled"),
        "docling_ocr_configured": primary_configured,
        "fallback_ocr_enabled": _enabled("fallback_ocr_enabled", "false"),
        "fallback_ocr_configured": fallback_configured,
        "fallback_ocr_available": fallback_available,
        # ── LLM Chat ──
        "primary_llm_enabled": _enabled("primary_llm_enabled"),
        "primary_llm_configured": primary_configured,
        "fallback_llm_enabled": _enabled("fallback_llm_enabled", "false"),
        "fallback_llm_configured": fallback_configured,
        "fallback_llm_available": fallback_available,
        "local_llm_enabled": _enabled("local_llm_enabled", "false"),
        "local_llm_configured": local_configured,
        # ── Translation (file-translate tool + transcript-EN; merged into one admin radio) ──
        "transcript_translation_provider": db.get_setting("transcript_translation_provider", "llm"),
        "translation_llm_provider": db.get_setting("translation_llm_provider", ""),
        "deepl_configured": bool(deepl_override) or bool(app_settings.deepl_api_key),
        "deepl_override_set": bool(deepl_override),
        "deepl_override_last_chars": _last6(deepl_override),
        "deepl_env_last_chars": _last6(env_deepl),
        # ── Provider model names (editable in the admin panel) ──
        "models": _current_models(),
        # ── UI labels (per locale; legacy unsuffixed keys fall back as DE defaults) ──
        "workspace_label_singular_de": db.get_setting(
            "workspace_label_singular_de",
            db.get_setting("workspace_label_singular", "Workspace"),
        ),
        "workspace_label_plural_de": db.get_setting(
            "workspace_label_plural_de",
            db.get_setting("workspace_label_plural", "Workspaces"),
        ),
        "workspace_label_singular_en": db.get_setting("workspace_label_singular_en", "Workspace"),
        "workspace_label_plural_en": db.get_setting("workspace_label_plural_en", "Workspaces"),
        # ── Hilde mascot (system-wide) ──
        "mascot_enabled": _enabled("mascot_enabled"),
    }


def _current_models() -> dict[str, str]:
    """Read current model names per provider/feature from DB."""
    from src.services.runtime_models import get_model, MODEL_KEYS
    return {key: get_model(key) for key in MODEL_KEYS}


# Simple bool setting keys: all set with the same schema
_SIMPLE_BOOL_FIELDS = (
    "whitelist_enabled",
    "elevenlabs_enabled", "kokoro_enabled", "mylab_enabled",
    "primary_whisper_enabled", "fallback_whisper_enabled",
    "primary_image_gen_enabled", "fallback_image_gen_enabled",
    "primary_image_analyze_enabled", "fallback_image_analyze_enabled",
    "primary_image_edit_enabled", "fallback_image_edit_enabled",
    "ocr_enabled",
    "docling_ocr_enabled", "fallback_ocr_enabled",
    "mascot_enabled",
)

# Radio fields: exactly one provider may be active at a time per group.
# Switching is a manual admin action — there is no automatic failover.
_EMBEDDING_KEYS = ("primary_embedding_enabled", "fallback_embedding_enabled", "local_embedding_enabled")
_LLM_KEYS = ("primary_llm_enabled", "fallback_llm_enabled", "local_llm_enabled")
_WHISPER_KEYS = ("primary_whisper_enabled", "fallback_whisper_enabled")
_IMAGE_GEN_KEYS = ("primary_image_gen_enabled", "fallback_image_gen_enabled")
_IMAGE_EDIT_KEYS = ("primary_image_edit_enabled", "fallback_image_edit_enabled")
_IMAGE_ANALYZE_KEYS = ("primary_image_analyze_enabled", "fallback_image_analyze_enabled")
_OCR_KEYS = ("docling_ocr_enabled", "fallback_ocr_enabled")


def _apply_radio_group(
    body_dict: dict, keys: tuple[str, ...], group_label: str, locale: str
) -> bool:
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
                    detail=t(
                        "admin.settings.lastProviderRequired",
                        locale,
                        group=group_label,
                    ),
                )
            db.set_setting(active_key, "false")
            changed = True
    return changed


@router.patch("/settings")
async def update_settings(
    body: UpdateSettingsRequest,
    _admin=Depends(get_admin_user),
    locale: str = Depends(get_locale),
):
    body_dict = body.model_dump()

    # Simple bool toggles
    for field in _SIMPLE_BOOL_FIELDS:
        val = body_dict.get(field)
        if val is not None:
            db.set_setting(field, "true" if val else "false")

    # Embeddings - exactly one must be enabled at any time.
    # Different embedding models have different vector dimensions, so parallel
    # operation would corrupt the index.
    if _apply_radio_group(body_dict, _EMBEDDING_KEYS, "Embedding", locale):
        invalidate_fingerprint_cache()

    # LLM Chat - exactly one must be enabled at any time.
    _apply_radio_group(body_dict, _LLM_KEYS, "LLM", locale)
    _apply_radio_group(body_dict, _WHISPER_KEYS, "Whisper", locale)
    _apply_radio_group(body_dict, _IMAGE_GEN_KEYS, "Image generation", locale)
    _apply_radio_group(body_dict, _IMAGE_EDIT_KEYS, "Image editing", locale)
    _apply_radio_group(body_dict, _IMAGE_ANALYZE_KEYS, "Image analysis", locale)
    _apply_radio_group(body_dict, _OCR_KEYS, "OCR", locale)

    # UI label overrides for "Workspace" (per UI locale)
    for label_key in (
        "workspace_label_singular_de",
        "workspace_label_plural_de",
        "workspace_label_singular_en",
        "workspace_label_plural_en",
    ):
        value = body_dict.get(label_key)
        if value is not None:
            stripped = value.strip()
            if not stripped:
                raise HTTPException(
                    status_code=400,
                    detail=t("admin.settings.labelEmpty", locale, label=label_key),
                )
            if len(stripped) > 40:
                raise HTTPException(
                    status_code=400,
                    detail=t("admin.settings.labelTooLong", locale, label=label_key),
                )
            db.set_setting(label_key, stripped)

    # Transcript translation: only "deepl" or "llm"
    if body.transcript_translation_provider is not None:
        if body.transcript_translation_provider not in ("deepl", "llm"):
            raise HTTPException(
                status_code=400,
                detail=t("translate.invalidProvider", locale),
            )
        db.set_setting("transcript_translation_provider", body.transcript_translation_provider)

    if body.deepl_api_key_override is not None:
        stripped = body.deepl_api_key_override.strip()
        if len(stripped) > 200:
            raise HTTPException(
                status_code=400,
                detail=t("admin.settings.deepl.keyTooLong", locale),
            )
        db.set_setting("deepl_api_key_override", stripped)

    # /translate LLM provider override (model values flow through the generic `models` dict)
    if body.translation_llm_provider is not None:
        prov = body.translation_llm_provider.strip()
        if prov and prov not in ("primary", "fallback", "local"):
            raise HTTPException(
                status_code=400,
                detail=t("translate.invalidProvider", locale),
            )
        db.set_setting("translation_llm_provider", prov)

    # Provider model names
    if body.models:
        from src.services.runtime_models import MODEL_KEYS
        unknown = [k for k in body.models if k not in MODEL_KEYS]
        if unknown:
            raise HTTPException(
                status_code=400,
                detail=t("admin.settings.unknownModelKeys", locale, unknown=unknown),
            )
        for key, value in body.models.items():
            stripped = (value or "").strip()
            if not stripped:
                raise HTTPException(
                    status_code=400,
                    detail=t("admin.settings.modelNameEmpty", locale, key=key),
                )
            db.set_setting(key, stripped)
        # Model change for embedding may require reindex
        if any(k in MODEL_KEYS and "embedding" in k for k in body.models):
            invalidate_fingerprint_cache()

    return {"ok": True}
