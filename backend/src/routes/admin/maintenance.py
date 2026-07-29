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
def set_maintenance(body: MaintenanceToggleRequest, _admin=Depends(get_admin_user)):
    db.set_setting("maintenance_mode", "true" if body.enabled else "false")
    logger.info("Maintenance mode set to {}", body.enabled)
    return {"ok": True, "enabled": body.enabled}


@router.post("/reindex-all")
def reindex_all(
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
