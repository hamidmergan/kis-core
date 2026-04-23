"""Admin-Jobs: globale Liste aller Jobs + Admin-Cancel."""

from fastapi import APIRouter, Depends, HTTPException, Query
from loguru import logger

from src import database as db
from src.celery_app import celery_app
from src.dependencies import get_admin_user
from src.storage import delete_job_folder

from src.routes.admin._registries import TOOL_LABELS, tools_matching_query

router = APIRouter(tags=["admin"])

# Screencast-Tools haben einen separaten render_started_at-Zeitstempel,
# der die reine ffmpeg-Laufzeit misst (Queue-Wartezeit ausgeschlossen).
_SCREENCAST_TOOLS = {"screencast_render", "screencast_auto", "screencast_demo_render", "screencast_translate"}


def _compute_duration(job: dict) -> float | None:
    """Dauer in Sekunden; bei Screencast-Tools ab render_started_at, sonst ab started_at."""
    if job["status"] != "success" or not job["completed_at"]:
        return None
    if job["tool"] in _SCREENCAST_TOOLS and job["render_started_at"]:
        return (job["completed_at"] - job["render_started_at"]).total_seconds()
    if job["started_at"]:
        return (job["completed_at"] - job["started_at"]).total_seconds()
    return None


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
    extra_tools = tools_matching_query(q) if q else None
    jobs, total = db.get_all_jobs(
        limit=limit, offset=offset, q=q,
        date_from=date_from.strip(), date_to=date_to.strip(),
        extra_tools=extra_tools,
    )
    result = [
        {
            "job_uuid": j["job_uuid"],
            "tool": j["tool"],
            "tool_label": TOOL_LABELS.get(j["tool"], j["tool"]),
            "original_filename": j["original_filename"],
            "status": j["status"],
            "error": j["error_message"],
            "created_at": j["created_at"],
            "completed_at": j["completed_at"],
            "duration_seconds": _compute_duration(j),
            "user_display_name": j.get("user_display_name") or j.get("ldap_username") or "Unbekannt",
        }
        for j in jobs
    ]
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
