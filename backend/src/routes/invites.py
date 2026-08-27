"""The public page of an invitation, the key in the link is the credential."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Response
from loguru import logger
from pydantic import BaseModel, Field

from src import database
from src.dependencies import get_session_store, get_settings
from src.ldap_admin import LdapUserExistsError, create_ldap_user
from src.features.invites import repository as repo
from src.features.invites.service import status_of
from src.i18n import get_locale, t

router = APIRouter(prefix="/invites", tags=["invites"])

MIN_PASSWORD_LENGTH = 8


def _open_invite_or_error(token: str, locale: str) -> dict:
    """Fetches the invitation and lets only an open one through."""
    if not get_settings().ldap_user_creation_enabled:
        raise HTTPException(status_code=404, detail=t("invite.featureDisabled", locale))

    invite = repo.get_invite_by_token(token)
    if invite is None:
        raise HTTPException(status_code=404, detail=t("invite.notFound", locale))

    zustand = status_of(
        used_at=invite["used_at"], expires_at=invite["expires_at"], now=datetime.now()
    )
    if zustand != "open":
        raise HTTPException(status_code=410, detail=t("invite.notValid", locale))
    return invite


@router.get("/{token}")
def read_invite(token: str, locale: str = Depends(get_locale)):
    invite = _open_invite_or_error(token, locale)
    return {"email": invite["email"], "uid": invite["uid"]}


class RedeemPayload(BaseModel):
    password: str = Field(..., min_length=1, max_length=128)
    given_name: str = Field("", max_length=64)
    surname: str = Field("", max_length=64)


@router.post("/{token}")
def redeem_invite(
    token: str,
    payload: RedeemPayload,
    response: Response,
    locale: str = Depends(get_locale),
):
    invite = _open_invite_or_error(token, locale)

    if len(payload.password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=t("invite.passwordTooShort", locale, min=MIN_PASSWORD_LENGTH),
        )

    vorname, nachname = payload.given_name.strip(), payload.surname.strip()
    display_name = " ".join(teil for teil in (vorname, nachname) if teil) or invite["uid"]

    # Invalidate the link first, then create, otherwise two attempts get through.
    if not repo.mark_invite_used(invite["id"]):
        raise HTTPException(status_code=410, detail=t("invite.notValid", locale))

    try:
        create_ldap_user(
            settings=get_settings(),
            uid=invite["uid"],
            given_name=vorname,
            surname=nachname,
            email=invite["email"],
            employee_type="staff" if invite["role"] == "staff" else "user",
            password=payload.password,
        )
    except Exception as fehler:
        # Nothing was created, so the link belongs to the person again.
        repo.reopen_invite(invite["id"])
        logger.error("invite redeem failed for uid={}: {}", invite["uid"], fehler)
        code = 409 if isinstance(fehler, LdapUserExistsError) else 500
        raise HTTPException(status_code=code, detail=t("invite.createFailed", locale))

    database.add_to_whitelist(invite["email"])
    user_id = database.create_user(
        ldap_username=invite["uid"],
        display_name=display_name,
        email=invite["email"],
        active=1,
        role=invite["role"],
    )
    if invite["role"] == "custom":
        database.set_user_role(user_id, "custom", invite["custom_role_id"])

    store = get_session_store()
    sitzung = store.create(data={
        "user_id": user_id,
        "username": invite["uid"],
        "display_name": display_name,
        "email": invite["email"],
        "role": invite["role"],
        "custom_role_id": invite["custom_role_id"],
    })
    response.set_cookie(
        key="session",
        value=sitzung,
        httponly=True,
        samesite="lax",
        max_age=86400,
        secure=get_settings().production,
    )
    logger.info("invite redeemed for uid={}", invite["uid"])
    return {"status": "ok", "username": invite["uid"], "display_name": display_name}
