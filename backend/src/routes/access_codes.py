"""The public side of the access codes, the code is the credential."""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response
from loguru import logger
from pydantic import BaseModel, Field

from src import database
from src.dependencies import get_session_store, get_settings
from src.features.access_codes import repository as repo
from src.features.access_codes.service import demo_email, normalize_code, status_of
from src.features.accounts.provisioning import provision_account
from src.features.accounts.uid import name_to_uid, unique_uid
from src.i18n import get_locale, t
from src.ldap_admin import LdapUserExistsError
from src.ldap_auth import authenticate_user

router = APIRouter(prefix="/access-codes", tags=["access codes"])

MIN_PASSWORD_LENGTH = 8
SESSION_MAX_AGE = 86400


def _require_feature(locale: str) -> None:
    """Access codes hang off the same switch as creating LDAP users."""
    if not get_settings().ldap_user_creation_enabled:
        raise HTTPException(status_code=404, detail=t("access.featureDisabled", locale))


def _live_code(code: str, locale: str, *, seat_needed: bool) -> dict:
    """Fetches the code and lets only a usable one through."""
    eintrag = repo.get_code_by_code(normalize_code(code))
    if eintrag is None:
        raise HTTPException(status_code=404, detail=t("access.codeUnknown", locale))

    zustand = status_of(
        active=eintrag["active"],
        used_count=eintrag["used_count"],
        max_uses=eintrag["max_uses"],
        valid_until=eintrag["valid_until"],
        now=datetime.now(),
    )
    # Renewing takes no seat, so a full code still renews.
    tot = zustand != "active" if seat_needed else zustand in ("disabled", "expired")
    if tot:
        raise HTTPException(status_code=410, detail=t("access.codeNotValid", locale))
    return eintrag


def _set_session(response: Response, daten: dict) -> None:
    """Puts the session into a cookie, same shape as the login."""
    token = get_session_store().create(data=daten)
    response.set_cookie(
        key="session",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=SESSION_MAX_AGE,
        secure=get_settings().production,
    )


@router.get("/enabled")
def feature_enabled():
    """Tells the public login page whether the link is worth showing."""
    return {"enabled": bool(get_settings().ldap_user_creation_enabled)}


class RedeemPayload(BaseModel):
    code: str = Field(..., min_length=3, max_length=32)
    given_name: str = Field(..., min_length=1, max_length=64)
    surname: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)


@router.post("/redeem")
def redeem(payload: RedeemPayload, response: Response, locale: str = Depends(get_locale)):
    _require_feature(locale)
    eintrag = _live_code(payload.code, locale, seat_needed=True)

    if len(payload.password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(
            status_code=400,
            detail=t("access.passwordTooShort", locale, min=MIN_PASSWORD_LENGTH),
        )

    basis = name_to_uid(payload.given_name, payload.surname)
    if basis is None:
        raise HTTPException(status_code=400, detail=t("access.nameUnusable", locale))
    uid = unique_uid(basis, lambda name: database.get_user_by_username(name) is not None)

    # Take the seat first, then create, otherwise the limit leaks under load.
    if not repo.claim_use(eintrag["id"]):
        raise HTTPException(status_code=410, detail=t("access.codeNotValid", locale))

    try:
        sitzungsdaten = provision_account(
            settings=get_settings(),
            uid=uid,
            given_name=payload.given_name,
            surname=payload.surname,
            email=demo_email(uid),
            role=eintrag["role"],
            custom_role_id=eintrag["custom_role_id"],
            password=payload.password,
        )
    except Exception as fehler:
        repo.release_use(eintrag["id"])
        logger.error("access code redeem failed for uid={}: {}", uid, fehler)
        code = 409 if isinstance(fehler, LdapUserExistsError) else 500
        raise HTTPException(status_code=code, detail=t("access.createFailed", locale))

    frist = datetime.now() + timedelta(days=eintrag["access_days"])
    repo.set_user_access(sitzungsdaten["user_id"], expires_at=frist, code_id=eintrag["id"])
    sitzungsdaten["access_expires_at"] = frist.isoformat()
    _set_session(response, sitzungsdaten)

    logger.info("access code redeemed for uid={} until={}", uid, frist.date())
    return {
        "status": "ok",
        "username": uid,
        "display_name": sitzungsdaten["display_name"],
        "expires_at": frist,
    }


class RenewPayload(BaseModel):
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1, max_length=128)
    code: str = Field(..., min_length=3, max_length=32)


@router.post("/renew")
def renew(payload: RenewPayload, response: Response, locale: str = Depends(get_locale)):
    _require_feature(locale)

    try:
        ldap_user = authenticate_user(payload.username.strip(), payload.password)
    except RuntimeError as fehler:
        logger.error("LDAP error while renewing '{}': {}", payload.username, fehler)
        raise HTTPException(status_code=500, detail=str(fehler))
    if ldap_user is None:
        raise HTTPException(status_code=401, detail=t("access.invalidCredentials", locale))

    konto = database.get_user_by_username(ldap_user["username"])
    if konto is None or konto.get("access_expires_at") is None:
        raise HTTPException(status_code=403, detail=t("access.notATestAccount", locale))

    eintrag = _live_code(payload.code, locale, seat_needed=False)
    frist = datetime.now() + timedelta(days=eintrag["access_days"])
    repo.set_user_access(konto["id"], expires_at=frist, code_id=eintrag["id"])

    _set_session(response, {
        "user_id": konto["id"],
        "username": ldap_user["username"],
        "display_name": konto.get("display_name") or ldap_user["username"],
        "email": konto.get("email") or "",
        "role": konto.get("role") or "user",
        "custom_role_id": konto.get("custom_role_id"),
        "access_expires_at": frist.isoformat(),
    })

    logger.info("access renewed for uid={} until={}", ldap_user["username"], frist.date())
    return {"status": "ok", "username": ldap_user["username"], "expires_at": frist}
