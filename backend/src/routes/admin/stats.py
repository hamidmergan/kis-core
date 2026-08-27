"""Stats endpoints: tool overview, activity log and AI assistant aggregates."""

from fastapi import APIRouter, Depends, HTTPException, Query

from src import database as db
from src.dependencies_rbac import require_permission
from src.features.stats import (
    assistant_overview,
    may_see_workspace,
    model_usage,
    own_workspaces,
    tool_overview,
    user_detail,
    user_overview,
    workspace_detail,
)
from src.permissions_registry import (
    PERM_SET_AIA_USAGE,
    PERM_SET_STATS_MODELS,
    PERM_SET_STATS_OWN,
    PERM_SET_STATS_USERS,
    PERM_SET_TOOLS_STATS,
)

from src.routes.admin._registries import TOOL_LABELS

router = APIRouter(tags=["admin: stats"])

# Two number pages, two rights.
_require_tool_stats = require_permission(PERM_SET_TOOLS_STATS)
_require_aia_usage = require_permission(PERM_SET_AIA_USAGE)
_require_stats_users = require_permission(PERM_SET_STATS_USERS)
_require_stats_models = require_permission(PERM_SET_STATS_MODELS)
_require_stats_own = require_permission(PERM_SET_STATS_OWN)


@router.get("/stats")
async def get_stats(
    days: int = Query(default=30, ge=1, le=365),
    _admin=Depends(_require_tool_stats),
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


@router.get("/ai-assistant/stats")
async def get_aia_stats(
    days: int = Query(default=30, ge=1, le=365),
    mode: str | None = Query(default=None, regex="^(source|glossary)$"),
    _admin=Depends(_require_aia_usage),
):
    """Aggregated KI-Assistent statistics for the admin dashboard."""
    return db.get_aia_admin_stats(days, mode=mode)


@router.get("/stats/users")
async def get_user_stats(_admin=Depends(_require_stats_users)):
    """Presence, intake and retention for the users tab."""
    return user_overview()


@router.get("/stats/models")
async def get_model_stats(
    days: int | None = Query(default=None, ge=1, le=3650),
    _admin=Depends(_require_stats_models),
):
    """Requests and tokens per model, without ``days`` over all time."""
    return model_usage(days)


@router.get("/stats/tools")
async def get_tool_stats(
    range: str = Query(default="alles", pattern="^(alles|jahr|30t)$"),
    _admin=Depends(_require_tool_stats),
):
    """Tiles, bars per tool and the weekday by hour grid."""
    return tool_overview(range)


@router.get("/stats/assistant")
async def get_assistant_stats(_admin=Depends(_require_aia_usage)):
    """Module, Materialien, Werkzeuge und Sprachniveau."""
    return assistant_overview()


@router.get("/stats/users/{user_id}")
async def get_user_detail(user_id: int, _admin=Depends(_require_stats_users)):
    """Everything about one person in one place."""
    daten = user_detail(user_id)
    if daten is None:
        raise HTTPException(status_code=404, detail="Unbekannter Nutzer")
    return daten


@router.get("/stats/workspaces/{uuid}")
async def get_workspace_detail(uuid: str, _admin=Depends(_require_aia_usage)):
    """Everything about one module in one place."""
    daten = workspace_detail(uuid)
    if daten is None:
        raise HTTPException(status_code=404, detail="Unbekanntes Modul")
    return daten


@router.get("/stats/eigene")
async def get_own_stats(user=Depends(_require_stats_own)):
    """The modules the caller owns or tutors."""
    return own_workspaces(user["user_id"])


@router.get("/stats/eigene/{uuid}")
async def get_own_workspace_detail(uuid: str, user=Depends(_require_stats_own)):
    """The same module, but only after the ownership check, otherwise 404."""
    if not may_see_workspace(uuid, user["user_id"]):
        raise HTTPException(status_code=404, detail="Unbekanntes Modul")
    daten = workspace_detail(uuid)
    if daten is None:
        raise HTTPException(status_code=404, detail="Unbekanntes Modul")
    return daten
