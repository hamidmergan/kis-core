"""User-Management: Liste/Approve und Whitelist-Verwaltung."""

from fastapi import APIRouter, Depends, HTTPException, Query

from src import database as db
from src.dependencies import get_admin_user

from src.routes.admin._models import AddWhitelistRequest

router = APIRouter(tags=["admin: users"])


# ── Users ─────────────────────────────────────────────────────────────────────

@router.get("/users")
async def list_users(
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0, ge=0),
    q: str = Query(default=""),
    date_from: str = Query(default=""),
    date_to: str = Query(default=""),
    _admin=Depends(get_admin_user),
):
    users, total = db.get_all_users(
        limit=limit, offset=offset, q=q.strip(),
        date_from=date_from.strip(), date_to=date_to.strip(),
    )
    return {"users": users, "total": total, "limit": limit, "offset": offset}


@router.get("/users/pending")
async def list_pending_users(_admin=Depends(get_admin_user)):
    return {"users": db.get_pending_users()}


@router.post("/users/{user_id}/approve")
async def approve_user(user_id: int, _admin=Depends(get_admin_user)):
    """Whitelist the user's email and set active=1 so they can log in immediately."""
    row = db.get_user_by_id(user_id)
    if not row:
        raise HTTPException(status_code=404, detail="User nicht gefunden")
    user = dict(row)
    if not user.get("email"):
        raise HTTPException(status_code=400, detail="User hat keine Email-Adresse")
    db.add_to_whitelist(user["email"])
    db.activate_user(user_id)
    return {"ok": True}


# ── Whitelist ──────────────────────────────────────────────────────────────────

@router.get("/whitelist")
async def list_whitelist(_admin=Depends(get_admin_user)):
    return {"emails": db.get_whitelist_emails()}


@router.post("/whitelist")
async def add_whitelist(body: AddWhitelistRequest, _admin=Depends(get_admin_user)):
    if not body.email or "@" not in body.email:
        raise HTTPException(status_code=400, detail="Ungültige Email-Adresse")
    db.add_to_whitelist(body.email)
    return {"ok": True}


@router.delete("/whitelist/{email:path}")
async def remove_whitelist(email: str, _admin=Depends(get_admin_user)):
    from src.dependencies import get_settings
    settings = get_settings()
    if email.strip().lower() == settings.admin_email.strip().lower():
        raise HTTPException(status_code=403, detail="Die Admin-Email kann nicht aus der Whitelist entfernt werden.")
    db.remove_from_whitelist(email)
    db.deactivate_user_by_email(email)
    return {"ok": True}
