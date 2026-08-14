"""User-Management: Liste/Approve und Whitelist-Verwaltung."""

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from src import database as db
from src.dependencies import get_settings
from src.dependencies_rbac import assert_may_grant, permissions_of, require_permission
from src.permissions_registry import (
    PERM_SET_USERS_ALL,
    PERM_SET_USERS_PENDING,
    PERM_SET_USERS_WHITELIST,
    SYSTEM_ROLE_PERMISSIONS,
)
from src.i18n import get_locale, t

from src.routes.admin._models import AddWhitelistRequest

router = APIRouter(tags=["admin: users"])

# Drei Seiten unter Nutzer, drei Rechte. Wer die Ausstehenden freischalten
# darf, muss deshalb noch lange nicht die ganze Nutzerliste sehen.
_require_users = require_permission(PERM_SET_USERS_ALL)
_require_pending = require_permission(PERM_SET_USERS_PENDING)
_require_whitelist = require_permission(PERM_SET_USERS_WHITELIST)


# ── Users ─────────────────────────────────────────────────────────────────────

@router.get("/users")
async def list_users(
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    q: str = Query(default=""),
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
    _admin=Depends(_require_users),
):
    users, total = db.get_all_users(
        limit=limit, offset=offset, q=q.strip(),
        date_from=date_from.strip(), date_to=date_to.strip(),
    )
    return {"users": users, "total": total, "limit": limit, "offset": offset}


@router.get("/users/pending")
async def list_pending_users(_admin=Depends(_require_pending)):
    return {"users": db.get_pending_users()}


@router.post("/users/{user_id}/approve")
async def approve_user(
    user_id: int,
    _admin=Depends(_require_pending),
    locale: str = Depends(get_locale),
):
    """Whitelist the user's email and set active=1 so they can log in immediately."""
    row = db.get_user_by_id(user_id)
    if not row:
        raise HTTPException(status_code=404, detail=t("admin.user.notFound", locale))
    user = dict(row)
    if not user.get("email"):
        raise HTTPException(status_code=400, detail=t("admin.user.noEmail", locale))
    db.add_to_whitelist(user["email"])
    db.activate_user(user_id)
    return {"ok": True}


# ── Whitelist ──────────────────────────────────────────────────────────────────

@router.get("/whitelist")
async def list_whitelist(_admin=Depends(_require_whitelist)):
    return {"emails": db.get_whitelist_emails()}


@router.post("/whitelist")
async def add_whitelist(
    body: AddWhitelistRequest,
    _admin=Depends(_require_whitelist),
    locale: str = Depends(get_locale),
):
    if not body.email or "@" not in body.email:
        raise HTTPException(
            status_code=400, detail=t("admin.whitelist.invalidEmail", locale)
        )
    db.add_to_whitelist(body.email)
    return {"ok": True}


@router.delete("/whitelist/{email:path}")
async def remove_whitelist(
    email: str,
    _admin=Depends(_require_whitelist),
    locale: str = Depends(get_locale),
):
    from src.dependencies import get_settings
    settings = get_settings()
    if email.strip().lower() == settings.admin_email.strip().lower():
        raise HTTPException(
            status_code=403,
            detail=t("admin.whitelist.adminProtected", locale),
        )
    db.remove_from_whitelist(email)
    db.deactivate_user_by_email(email)
    return {"ok": True}


# ── User Role Assignment ───────────────────────────────────────────────────────

class UpdateUserRoleBody(BaseModel):
    role: str
    custom_role_id: int | None = None


@router.post("/users/{user_id}/role")
async def update_user_role(
    user_id: int,
    body: UpdateUserRoleBody,
    admin=Depends(_require_users),
    locale: str = Depends(get_locale),
):
    """Update a user's role.

    Safety rules:
    - Cannot change the env-admin's role.
    - Man kann nur eine Rolle vergeben, deren Rechte man selbst hat. Ohne diese
      Regel waere "Alle Nutzer" ein Weg zum Administrator: sich selbst oder
      einem Zweitkonto die Rolle Administrator geben und fertig.
    """
    target = db.get_user_by_id(user_id)
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")

    settings = get_settings()
    target_email = (target.get("email") or "").lower()
    if settings.admin_email and target_email == settings.admin_email.lower():
        raise HTTPException(status_code=400, detail="Cannot change role of the env-admin")

    if body.role == "custom":
        role_row = db.get_custom_role(body.custom_role_id) if body.custom_role_id else None
        granted = role_row["permissions"] if role_row else []
    else:
        granted = SYSTEM_ROLE_PERMISSIONS.get(body.role, ())
    assert_may_grant(permissions_of(admin), granted, locale)

    try:
        db.set_user_role(user_id, body.role, body.custom_role_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"status": "ok"}
