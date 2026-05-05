"""Read-only system info endpoint.

Exposes the current limits, active models, RAG/retrieval params, parallelism
and timeouts so the admin can verify what the system is actually running
without digging through the codebase. No PATCH on purpose: tuning these is
code-level work, this is a transparency surface.
"""

import os

from fastapi import APIRouter, Depends

from src import database as db
from src import limits as L
from src.dependencies import get_admin_user
from src.services.runtime_models import MODEL_DEFAULTS, get_model

router = APIRouter(tags=["admin: system-info"])


def _enabled(key: str, default: str = "true") -> bool:
    return db.get_setting(key, default).lower() == "true"


def _active_provider(group: tuple[str, ...]) -> str | None:
    """Return the *_enabled key whose value is currently true, stripped of suffix."""
    for key in group:
        if _enabled(key, "false"):
            return key.removesuffix("_enabled")
    return None


# Provider selection groups (mirrors settings.py).
_LLM_GROUP = ("primary_llm_enabled", "fallback_llm_enabled", "local_llm_enabled")
_EMBED_GROUP = (
    "primary_embedding_enabled",
    "fallback_embedding_enabled",
    "local_embedding_enabled",
)
_OCR_GROUP = ("primary_ocr_enabled", "fallback_ocr_enabled")
_IMAGE_GEN_GROUP = ("primary_image_gen_enabled", "fallback_image_gen_enabled")
_IMAGE_EDIT_GROUP = ("primary_image_edit_enabled", "fallback_image_edit_enabled")
_IMAGE_ANALYZE_GROUP = ("primary_image_analyze_enabled", "fallback_image_analyze_enabled")
_WHISPER_GROUP = ("primary_whisper_enabled", "fallback_whisper_enabled")


def _model_for(provider: str | None, key_suffix: str) -> str | None:
    """Resolve the active model name for a provider+capability, or None."""
    if not provider:
        return None
    key = f"{provider}_{key_suffix}"
    if key in MODEL_DEFAULTS:
        return get_model(key)
    return None


@router.get("/system-info")
async def get_system_info(_admin=Depends(get_admin_user)):
    # ── Active models per capability ───────────────────────────────────
    llm_provider = _active_provider(_LLM_GROUP)
    embed_provider = _active_provider(_EMBED_GROUP)
    ocr_provider = _active_provider(_OCR_GROUP)
    image_gen_provider = _active_provider(_IMAGE_GEN_GROUP)
    image_edit_provider = _active_provider(_IMAGE_EDIT_GROUP)
    image_analyze_provider = _active_provider(_IMAGE_ANALYZE_GROUP)
    whisper_provider = _active_provider(_WHISPER_GROUP)

    tts_active = [
        name for name, key in (
            ("ElevenLabs", "elevenlabs_enabled"),
            ("Kokoro", "kokoro_enabled"),
            ("myLab", "mylab_enabled"),
        ) if _enabled(key, "false")
    ]

    models = {
        "llm": {"provider": llm_provider, "model": _model_for(llm_provider, "llm_model")},
        "embedding": {"provider": embed_provider, "model": _model_for(embed_provider, "embedding_model")},
        "ocr": {"provider": ocr_provider, "model": _model_for(ocr_provider, "ocr_model")},
        "image_gen": {"provider": image_gen_provider, "model": _model_for(image_gen_provider, "image_gen_model")},
        "image_edit": {"provider": image_edit_provider, "model": _model_for(image_edit_provider, "image_edit_model")},
        "image_analyze": {"provider": image_analyze_provider, "model": _model_for(image_analyze_provider, "image_analyze_model")},
        "whisper": {"provider": whisper_provider, "model": None},
        "tts_active": tts_active,
        "tts_mylab_model": get_model("mylab_tts_model") if _enabled("mylab_enabled", "false") else None,
    }

    # ── Rate limits ────────────────────────────────────────────────────
    rate_limits = {
        "chat_burst_requests": L.RATE_LIMIT_BURST_REQUESTS,
        "chat_burst_window_seconds": L.RATE_LIMIT_BURST_WINDOW_SECONDS,
        "chat_block_minutes": L.RATE_LIMIT_BLOCK_MINUTES,
        "tool_burst_requests": L.TOOL_BURST_REQUESTS,
        "tool_burst_window_seconds": L.TOOL_BURST_WINDOW_SECONDS,
        "tool_block_minutes": L.TOOL_BURST_BLOCK_MINUTES,
    }

    # ── Quotas (mirrors current defaults; per-user overrides exist in `quota` tab) ──
    quotas = [
        {"key": k, "label": v["label"], "limit": v["limit"], "window_hours": v["window_hours"]}
        for k, v in L.QUOTA_DEFAULTS.items()
    ]

    # ── Upload sizes ───────────────────────────────────────────────────
    uploads = {
        "general_mb": L.MAX_UPLOAD_BYTES // (1024 * 1024),
        "translate_mb": L.TRANSLATE_MAX_UPLOAD_BYTES // (1024 * 1024),
        "transcription_mb": L.MAX_TRANSCRIPTION_BYTES // (1024 * 1024),
        "image_mb": L.MAX_IMAGE_BYTES // (1024 * 1024),
        "output_video_mb": L.MAX_OUTPUT_VIDEO_BYTES // (1024 * 1024),
    }

    char_limits = {
        "tts": L.TTS_MAX_CHARS,
        "translate": L.TRANSLATE_MAX_CHARS,
        "summary": L.SUMMARY_MAX_CHARS,
        "screencast": L.SCREENCAST_MAX_CHARS,
        "script": L.SCRIPT_MAX_CHARS,
    }

    # ── Workspace / source / KI-Tutor object limits ────────────────────
    workspace_limits = {
        "max_sources_per_workspace": L.AIA_WORKSPACE_MAX_SOURCES,
        "max_pages_per_source": L.AIA_SOURCE_MAX_PAGES,
        "max_access_links": L.AIA_WORKSPACE_MAX_ACCESS_LINKS,
        "max_notes_per_user": L.AIA_NOTES_MAX_PER_USER,
        "glossary_limit": L.GLOSSARY_LIMIT,
        "max_screencast_slides": L.MAX_SCREENCAST_SLIDES,
        "max_queued_screencast_jobs": L.MAX_QUEUED_SCREENCAST_JOBS,
    }

    # ── RAG retrieval (hardcoded in chunks.py + chat.py) ───────────────
    rag = {
        "vector_top_k": 40,
        "keyword_top_k": 40,
        "ilike_fallback_top_k": 20,
        "rrf_k": 60,
        "final_chunks_used": 20,
        "embed_batch_size": 20,
    }

    # ── KI-Tutor page-summary pipeline ─────────────────────────────────
    summaries = {
        "max_retries": L.AIA_SUMMARY_MAX_RETRIES,
        "timeout_small_seconds": L.AIA_SUMMARY_TIMEOUT_SMALL,
        "timeout_large_seconds": L.AIA_SUMMARY_TIMEOUT_LARGE,
        "max_tokens_small": L.AIA_SUMMARY_MAX_TOKENS_SMALL,
        "max_tokens_large": L.AIA_SUMMARY_MAX_TOKENS_LARGE,
        "max_tokens_batch": L.AIA_SUMMARY_MAX_TOKENS_BATCH,
        "content_max_chars_per_page": L.AIA_SUMMARY_CONTENT_MAX_CHARS,
        "parallel_workers_small": L.AIA_SUMMARY_PARALLEL_WORKERS_SMALL,
        "parallel_workers_large": L.AIA_SUMMARY_PARALLEL_WORKERS_LARGE,
        "batch_size_pages": L.AIA_SUMMARY_BATCH_SIZE,
    }

    # ── Job/result management ──────────────────────────────────────────
    jobs = {
        "max_result_files_per_user": L.MAX_RESULT_FILES,
        "retention_hours": L.JOB_RETENTION_HOURS,
        "watchdog_minutes": L.JOB_WATCHDOG_MINUTES,
    }

    # ── Celery task timeouts ───────────────────────────────────────────
    celery_timeouts = {
        "tts_soft_seconds": L.TTS_SOFT_TIME_LIMIT,
        "tts_hard_seconds": L.TTS_TIME_LIMIT,
        "screencast_soft_seconds": L.SCREENCAST_SOFT_TIME_LIMIT,
        "screencast_hard_seconds": L.SCREENCAST_TIME_LIMIT,
    }

    # ── Render / process parallelism ───────────────────────────────────
    parallelism = {
        "render_workers": L.RENDER_MAX_WORKERS,
        "cpu_count": os.cpu_count() or 0,
    }

    # ── DB pool ────────────────────────────────────────────────────────
    database = {"pool_min": 1, "pool_max": 20}

    return {
        "models": models,
        "rate_limits": rate_limits,
        "quotas": quotas,
        "uploads": uploads,
        "char_limits": char_limits,
        "workspace_limits": workspace_limits,
        "rag": rag,
        "summaries": summaries,
        "jobs": jobs,
        "celery_timeouts": celery_timeouts,
        "parallelism": parallelism,
        "database": database,
    }
