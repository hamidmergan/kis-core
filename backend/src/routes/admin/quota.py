"""Quota-Verwaltung: globale Defaults, per-User Overview und per-Type Overrides."""

from fastapi import APIRouter, Depends, HTTPException

from src import database as db
from src.dependencies import get_admin_user
from src.limits import QUOTA_DEFAULTS

from src.routes.admin._models import SetQuotaOverrideRequest

router = APIRouter(tags=["admin"])


def _iso_z(ts) -> str | None:
    return (ts.isoformat() + "Z") if ts else None


def _ensure_known_quota_type(quota_type: str) -> None:
    if quota_type not in QUOTA_DEFAULTS:
        raise HTTPException(status_code=400, detail=f"Unbekannter Quota-Typ: {quota_type}")


@router.get("/quota/defaults")
async def get_quota_defaults(_admin=Depends(get_admin_user)):
    """Globale Standard-Limits anzeigen."""
    return {"defaults": QUOTA_DEFAULTS}


@router.get("/quota/overview")
async def get_quota_overview(_admin=Depends(get_admin_user)):
    """Alle aktiven User mit Kontingenten (auch ohne bisherige Aktivität)."""
    rows = db.quota_get_all_users_usage()
    users: dict[int, dict] = {}
    for row in rows:
        uid = row["user_id"]
        if uid not in users:
            users[uid] = {
                "user_id": uid,
                "ldap_username": row["ldap_username"],
                "display_name": row["display_name"],
                "quotas": [],
                "global_reset_at": row.get("global_reset_at"),
            }
        if row["quota_type"] is None:
            # User exists but has no quota entries yet — fill from QUOTA_DEFAULTS
            for cfg_type, cfg in QUOTA_DEFAULTS.items():
                effective_limit = cfg["limit"]
                users[uid]["quotas"].append({
                    "quota_type": cfg_type,
                    "label": cfg["label"],
                    "used": 0,
                    "limit": effective_limit,
                    "limit_is_unlimited": effective_limit == -1,
                    "override": None,
                    "reset_at": None,
                })
        else:
            cfg = QUOTA_DEFAULTS.get(row["quota_type"], {})
            effective_limit = row["override"] if row["override"] is not None else cfg.get("limit", 30)
            users[uid]["quotas"].append({
                "quota_type": row["quota_type"],
                "label": cfg.get("label", row["quota_type"]),
                "used": row["used"],
                "limit": effective_limit,
                "limit_is_unlimited": effective_limit == -1,
                "override": row["override"],
                "reset_at": _iso_z(row["reset_at"]),
            })
    return {"users": list(users.values())}


@router.get("/quota/users/{user_id}")
async def get_user_quota(user_id: int, _admin=Depends(get_admin_user)):
    """Alle Quota-Typen für einen bestimmten User."""
    rows, global_reset_at = db.quota_get_all_for_user(user_id)
    result = []
    for cfg_type, cfg in QUOTA_DEFAULTS.items():
        row = next((r for r in rows if r["quota_type"] == cfg_type), None)
        used = row["used"] if row else 0
        override = row["override"] if row else None
        reset_at = row["reset_at"] if row else None
        effective_limit = override if override is not None else cfg["limit"]
        result.append({
            "quota_type": cfg_type,
            "label": cfg["label"],
            "used": used,
            "limit": effective_limit,
            "limit_is_unlimited": effective_limit == -1,
            "override": override,
            "reset_at": _iso_z(reset_at),
        })
    return {
        "user_id": user_id,
        "quotas": result,
        "global_reset_at": _iso_z(global_reset_at),
    }


@router.post("/quota/users/{user_id}/{quota_type}/override")
async def set_quota_override(
    user_id: int,
    quota_type: str,
    body: SetQuotaOverrideRequest,
    _admin=Depends(get_admin_user),
):
    """Per-User Limit setzen. -1 = unlimitiert."""
    _ensure_known_quota_type(quota_type)
    db.quota_set_override(user_id, quota_type, body.limit_value)
    return {"ok": True}


@router.delete("/quota/users/{user_id}/{quota_type}/override")
async def delete_quota_override(
    user_id: int,
    quota_type: str,
    _admin=Depends(get_admin_user),
):
    """Override löschen — User fällt auf globalen Standard zurück."""
    _ensure_known_quota_type(quota_type)
    db.quota_remove_override(user_id, quota_type)
    return {"ok": True}


@router.post("/quota/users/{user_id}/{quota_type}/reset")
async def reset_user_quota(
    user_id: int,
    quota_type: str,
    _admin=Depends(get_admin_user),
):
    """Quota-Zähler sofort auf 0 setzen und Reset-Timer löschen."""
    _ensure_known_quota_type(quota_type)
    db.quota_reset(user_id, quota_type)
    return {"ok": True}
