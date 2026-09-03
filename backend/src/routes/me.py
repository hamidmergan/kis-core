from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src import database as db
from src.dependencies import get_current_user
from src.i18n import get_locale, t

router = APIRouter(prefix="/me", tags=["me"])


class LocaleUpdate(BaseModel):
    locale: str = Field(pattern=r"^(de|en)$")


class TourSeenUpdate(BaseModel):
    """false releases the tour again, then the invitation comes back."""
    seen: bool


@router.get("")
async def get_me(
    user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail=t("auth.notAuthenticated", locale))
    row = db.get_user_by_id(user_id)
    if not row:
        raise HTTPException(status_code=404, detail=t("user.notFound", locale))
    ll = db.get_user_language_level(user_id)
    set_at = ll["language_level_set_at"]
    return {
        "id": row["id"],
        "username": row["ldap_username"],
        "display_name": row["display_name"],
        "email": row["email"],
        "role": row["role"],
        "locale": row.get("locale", "de"),
        "language_level": ll["language_level"],
        "language_level_set_at": set_at.isoformat() if set_at else None,
        "tour_seen_at": row["tour_seen_at"].isoformat() if row.get("tour_seen_at") else None,
    }


@router.post("/tour-seen")
async def update_tour_seen(
    payload: TourSeenUpdate,
    user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Remembers per account whether the tour was done, so it survives a browser change."""
    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail=t("auth.notAuthenticated", locale))
    db.set_user_tour_seen(user_id, payload.seen)
    return {"seen": payload.seen}


@router.patch("/locale")
async def update_locale(
    payload: LocaleUpdate,
    user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail=t("auth.notAuthenticated", locale))
    db.update_user_locale(user_id, payload.locale)
    return {"locale": payload.locale}
