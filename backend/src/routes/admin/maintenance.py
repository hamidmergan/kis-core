"""Maintenance mode, stale fingerprint check, and reindex trigger."""

import asyncio
import json

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from src import database as db
from src.dependencies import get_admin_user
from src.i18n import get_locale, t

from src.routes.admin._embedding import active_embedding_provider_key, get_cached_fingerprint
from src.routes.admin._models import MaintenanceToggleRequest

router = APIRouter(tags=["admin: maintenance"])


@router.get("/maintenance")
async def get_maintenance(_admin=Depends(get_admin_user)):
    enabled = db.get_setting("maintenance_mode", "false").lower() == "true"
    try:
        progress = json.loads(db.get_setting("reindex_progress", "") or "null")
    except Exception:
        progress = None

    # Read fingerprint from DB only - do NOT compute on demand (compute takes
    # 15-50s against KISSKI cold). If not cached yet, fire a background task
    # to prime it; the user's next page refresh will see the stale_workspaces.
    key = f"fingerprint_{active_embedding_provider_key()}"
    current_fingerprint = db.get_setting(key, "") or None
    stale_workspaces: list[dict] = []
    if current_fingerprint:
        try:
            stale_workspaces = db.list_aia_workspaces_with_stale_fingerprint(current_fingerprint)
        except Exception as e:
            logger.warning("Maintenance: stale-workspace query failed: {}", e)
    else:
        # Prime the cache in the background - endpoint stays fast.
        asyncio.create_task(asyncio.to_thread(get_cached_fingerprint))

    return {
        "enabled": enabled,
        "reindex": progress,
        "stale_workspaces": stale_workspaces,
        "fingerprint_check_ok": bool(current_fingerprint),
    }


@router.post("/maintenance")
async def set_maintenance(body: MaintenanceToggleRequest, _admin=Depends(get_admin_user)):
    db.set_setting("maintenance_mode", "true" if body.enabled else "false")
    logger.info("Maintenance mode set to {}", body.enabled)
    return {"ok": True, "enabled": body.enabled}


@router.post("/reindex-all")
async def reindex_all(
    _admin=Depends(get_admin_user),
    locale: str = Depends(get_locale),
):
    """Queue a Celery job to re-embed every KI-Assistent chunk with the current provider."""
    progress_raw = db.get_setting("reindex_progress", "") or ""
    try:
        progress = json.loads(progress_raw) if progress_raw else None
    except Exception:
        progress = None
    if progress and progress.get("running"):
        raise HTTPException(
            status_code=409,
            detail=t("admin.maintenance.reindexAlreadyRunning", locale),
        )

    from src.tasks.aia_tasks import run_reindex_all_sources
    db.set_setting("reindex_progress", json.dumps({
        "total": 0, "done": 0, "current": "queued", "failed": 0, "running": True,
    }))
    run_reindex_all_sources.delay()
    return {"ok": True}


@router.get("/backfill-doc-summaries")
async def backfill_doc_summaries_status(_admin=Depends(get_admin_user)):
    """How many ready sources are still missing a doc-summary?"""
    from src.core.db.pool import get_connection
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(*) FROM aia_sources WHERE status = 'ready' AND (summary IS NULL OR summary = '')"
            )
            pending = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM aia_sources WHERE status = 'ready'")
            total = cur.fetchone()[0]
    return {"pending": pending, "total": total}


@router.post("/backfill-doc-summaries")
async def backfill_doc_summaries(_admin=Depends(get_admin_user)):
    """Queue a one-shot job that generates doc-summaries for every source missing one."""
    from src.tasks.aia_tasks import run_backfill_doc_summaries
    run_backfill_doc_summaries.delay()
    return {"ok": True}


@router.get("/backfill-page-summaries")
async def backfill_page_summaries_status(_admin=Depends(get_admin_user)):
    """How many ready PDF sources are still missing page-summaries?"""
    from src.core.db.pool import get_connection
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT COUNT(*) FROM aia_sources s
                   WHERE s.status = 'ready' AND s.file_type = 'pdf'
                     AND NOT EXISTS (
                       SELECT 1 FROM aia_page_summaries p WHERE p.source_id = s.id
                     )"""
            )
            pending = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM aia_sources WHERE status = 'ready' AND file_type = 'pdf'")
            total = cur.fetchone()[0]
    return {"pending": pending, "total": total}


@router.post("/backfill-page-summaries")
async def backfill_page_summaries(_admin=Depends(get_admin_user)):
    """Queue a one-shot job that generates page-summaries for every PDF missing them.

    Each PDF is dispatched as a separate ``run_generate_summaries`` task; that
    task chains a fresh doc-summary at completion, so multi-source GENERIC
    chat will end up with accurate page-number citations on the next ask.
    """
    from src.tasks.aia_tasks import run_backfill_page_summaries
    run_backfill_page_summaries.delay()
    return {"ok": True}
