"""Admin creates a reset link for a user, the old password stays valid until it is used."""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from src import database
from src.dependencies import get_settings
from src.dependencies_rbac import require_permission
from src.features.password_reset import repository as repo
from src.features.password_reset.service import (
    VALID_DAYS,
    can_get_reset_link,
    hash_token,
    new_token,
)
from src.i18n import get_locale, t
from src.permissions_registry import PERM_SET_USERS_ALL

router = APIRouter(tags=["admin: password reset"])

_require = require_permission(PERM_SET_USERS_ALL)


@router.post("/users/{user_id}/reset-link")
def create_reset_link(
    user_id: int,
    admin: dict = Depends(_require),
    locale: str = Depends(get_locale),
):
    """Returns the key once, only its hash is stored, the password itself is not touched."""
    konto = database.get_user_by_id(user_id)
    if not konto:
        raise HTTPException(status_code=404, detail=t("passwordReset.userNotFound", locale))
    if not can_get_reset_link(dict(konto), get_settings().admin_email):
        raise HTTPException(status_code=403, detail=t("passwordReset.notAllowed", locale))

    token = new_token()
    expires_at = datetime.now() + timedelta(days=VALID_DAYS)
    repo.create_token(
        token_hash=hash_token(token),
        user_id=user_id,
        created_by=admin.get("user_id"),
        expires_at=expires_at,
    )
    logger.info("admin {} created a reset link for user_id={}", admin.get("email"), user_id)
    return {"token": token, "expires_at": expires_at}
