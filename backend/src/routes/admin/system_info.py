"""Read-only system info endpoint.

Exposes the current limits, active models, RAG/retrieval params, parallelism
and timeouts so the admin can verify what the system is actually running
without digging through the codebase. No PATCH on purpose: tuning these is
code-level work, this is a transparency surface.
"""

import os

from fastapi import APIRouter, Depends

from src import limits as L
from src.dependencies import get_admin_user
from src.services import feature_router

router = APIRouter(tags=["admin: system-info"])


def _binding_view(feature: str) -> dict | None:
    """Render a feature's active binding as ``{provider, model}`` or None."""
    try:
        binding = feature_router.resolve(feature)
    except feature_router.FeatureNotConfigured:
        return None
    return {
        "provider": binding.provider.get("name"),
        "model": binding.model or None,
    }


def _user_choice_view(feature: str) -> list[dict]:
    """List of providers the admin enabled for end-user multi-pick on ``feature``."""
    rows = feature_router.providers_for_feature(feature)
    return [{"provider": r.get("name"), "protocol": r.get("protocol")} for r in rows]


def _empty_binding() -> dict:
    """Fallback row when a feature route is unconfigured. Keeps the response
    shape stable so the frontend doesn't need to null-check every field."""
    return {"provider": None, "model": None}


@router.get("/system-info")
async def get_system_info(_admin=Depends(get_admin_user)):
    # ── Active bindings per feature route ──────────────────────────────
    tts_providers = _user_choice_view("tts")
    models = {
        "llm": _binding_view("chat") or _empty_binding(),
        "embedding": _binding_view("embedding") or _empty_binding(),
        "ocr": _binding_view("ocr") or _empty_binding(),
        "image_gen": _binding_view("image_gen") or _empty_binding(),
        "image_edit": _binding_view("image_edit") or _empty_binding(),
        "image_analyze": _binding_view("vision") or _empty_binding(),
        "whisper": _binding_view("stt") or _empty_binding(),
        # Backward-compatible list of TTS provider names for the existing UI.
        "tts_active": [p["provider"] for p in tts_providers if p.get("provider")],
        "tts_mylab_model": None,
        "doc_translate": _user_choice_view("doc_translate"),
        "screencast_translate": _user_choice_view("screencast_translate"),
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
