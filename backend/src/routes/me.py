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


class LanguageTrainingUpdate(BaseModel):
    """The one switch, yes on the start question or the toggle in the profile."""
    active: bool


def _language_training_state(user_id: int) -> dict:
    """The three fields the profile and the start question read."""
    state = db.get_user_language_training(user_id)
    asked = state["language_training_asked_at"]
    return {
        "language_training_enabled": db.is_language_training_enabled_globally(),
        "language_training_active": state["language_training_active"],
        "language_training_asked_at": asked.isoformat() if asked else None,
    }


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
        **_language_training_state(user_id),
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


@router.patch("/language-training")
async def update_language_training(
    payload: LanguageTrainingUpdate,
    user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    """Answers the start question or flips the profile switch, the admin switch gates it."""
    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail=t("auth.notAuthenticated", locale))
    if not db.is_language_training_enabled_globally():
        raise HTTPException(status_code=403, detail=t("ai.languageTraining.disabled", locale))
    db.set_user_language_training(user_id, payload.active)
    return _language_training_state(user_id)


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
