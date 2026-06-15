"""Per-user terminology glossaries (translation tool).

CRUD over the user's own glossaries, persisted in the DB. Replaces the former
browser-only (localStorage) storage so glossaries survive across devices and
browser resets. Every endpoint is scoped to the authenticated user; there is
no sharing between users.
"""

from fastapi import APIRouter, Depends, HTTPException

from src import database as db
from src.dependencies import get_current_user
from src.features.glossaries.schemas import GlossaryCreate, GlossaryUpdate
from src.i18n import get_locale, t
from src.limits import GLOSSARY_MAX_COUNT

router = APIRouter(prefix="/glossaries", tags=["glossaries"])


def _require_user_id(user: dict, locale: str) -> int:
    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail=t("auth.notAuthenticated", locale))
    return user_id


@router.get("")
async def list_glossaries(
    user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    user_id = _require_user_id(user, locale)
    return db.list_user_glossaries(user_id)


@router.post("")
async def create_glossary(
    payload: GlossaryCreate,
    user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    user_id = _require_user_id(user, locale)
    if db.count_user_glossaries(user_id) >= GLOSSARY_MAX_COUNT:
        raise HTTPException(
            status_code=409,
            detail=t("glossary.tooMany", locale, max=GLOSSARY_MAX_COUNT),
        )
    return db.create_user_glossary(user_id, payload.name, payload.entries)


@router.patch("/{glossary_id}")
async def update_glossary(
    glossary_id: str,
    payload: GlossaryUpdate,
    user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    user_id = _require_user_id(user, locale)
    updated = db.update_user_glossary(
        user_id, glossary_id, name=payload.name, entries=payload.entries
    )
    if updated is None:
        raise HTTPException(status_code=404, detail=t("glossary.notFound", locale))
    return updated


@router.delete("/{glossary_id}")
async def delete_glossary(
    glossary_id: str,
    user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
):
    user_id = _require_user_id(user, locale)
    if not db.delete_user_glossary(user_id, glossary_id):
        raise HTTPException(status_code=404, detail=t("glossary.notFound", locale))
    return {"ok": True}
