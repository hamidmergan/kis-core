"""Stats-Endpoints: Tool-Übersicht, Aktivitätslog und KI-Assistent-Aggregate."""

from fastapi import APIRouter, Depends, Query

from src import database as db
from src.dependencies import get_admin_user

from src.routes.admin._registries import TOOL_LABELS

router = APIRouter(tags=["admin"])


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
            tools[t] = {"tool": t, "label": TOOL_LABELS.get(t, t), "total": 0, "success": 0, "failed": 0}
        tools[t]["total"] += row["cnt"]
        if row["status"] == "success":
            tools[t]["success"] = row["cnt"]
        elif row["status"] == "failed":
            tools[t]["failed"] = row["cnt"]

    for info in tools.values():
        info["avg_seconds"] = raw["avg_duration"].get(info["tool"])

    activity = db.get_job_activity_log(days, limit=50)
    for a in activity:
        a["tool_label"] = TOOL_LABELS.get(a["tool"], a["tool"])

    return {
        "by_tool": sorted(tools.values(), key=lambda x: x["total"], reverse=True),
        "activity": activity,
        "days": days,
    }


@router.get("/ki-assistent/stats")
async def get_kia_stats(
    days: int = Query(default=30, ge=1, le=365),
    mode: str | None = Query(default=None, regex="^(quelle|glossar)$"),
    _admin=Depends(get_admin_user),
):
    """Aggregated KI-Assistent statistics for the admin dashboard."""
    return db.get_kia_admin_stats(days, mode=mode)
