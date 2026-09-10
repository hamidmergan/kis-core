"""Create, list, switch off and delete access codes for test rounds."""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, Field, model_validator

from src import database
from src.dependencies import get_settings
from src.dependencies_rbac import assert_may_grant, permissions_of, require_permission
from src.features.access_codes import repository as repo
from src.features.access_codes.service import new_code, status_of, user_status_of
from src.features.accounts.passwords import generate_password, hash_password
from src.i18n import get_locale, t
from src.permissions_registry import PERM_SET_USERS_ALL, SYSTEM_ROLE_PERMISSIONS

router = APIRouter(tags=["admin: access codes"])

_require = require_permission(PERM_SET_USERS_ALL)

MAX_VALID_DAYS = 60
MAX_ACCESS_HOURS = 720  # 30 Tage
MAX_SEATS = 500


def _require_feature(locale: str) -> None:
    """Access codes hang off the same switch as creating LDAP users."""
    if not get_settings().account_creation_enabled:
        raise HTTPException(status_code=404, detail=t("access.featureDisabled", locale))


class CreateCodePayload(BaseModel):
    label: str = Field(..., min_length=1, max_length=64)
    max_uses: int = Field(50, ge=1, le=MAX_SEATS)
    valid_days: int = Field(30, ge=1, le=MAX_VALID_DAYS)
    access_hours: int | None = Field(336)
    show_credentials: bool = True
    show_evaluation: bool = False
    kis_role: str = Field("user", pattern="^(staff|user|custom)$")
    custom_role_id: int | None = None

    @model_validator(mode="after")
    def _label_and_role(self):
        if not self.label.strip():
            raise ValueError("label must not be blank")
        self.label = self.label.strip()
        if self.access_hours is not None and not (1 <= self.access_hours <= MAX_ACCESS_HOURS):
            raise ValueError(f"access_hours must be between 1 and {MAX_ACCESS_HOURS}")
        if self.kis_role == "custom" and self.custom_role_id is None:
            raise ValueError("custom_role_id required when kis_role is 'custom'")
        if self.kis_role != "custom":
            self.custom_role_id = None
        return self


class PatchCodePayload(BaseModel):
    active: bool | None = None
    label: str | None = Field(None, min_length=1, max_length=64)
    max_uses: int | None = Field(None, ge=1, le=MAX_SEATS)
    valid_days: int | None = Field(None, ge=1, le=MAX_VALID_DAYS)
    access_hours: int | None = None
    show_credentials: bool = True
    show_evaluation: bool = False
    kis_role: str | None = Field(None, pattern="^(staff|user|custom)$")
    custom_role_id: int | None = None

    @model_validator(mode="after")
    def _edit_fields_travel_together(self):
        bearbeitungsfelder = (self.label, self.max_uses, self.valid_days, self.kis_role)
        if any(f is not None for f in bearbeitungsfelder) and not all(f is not None for f in bearbeitungsfelder):
            raise ValueError("label, max_uses, valid_days and kis_role must be provided together")
        if self.label is not None:
            if not self.label.strip():
                raise ValueError("label must not be blank")
            self.label = self.label.strip()
        if self.access_hours is not None and not (1 <= self.access_hours <= MAX_ACCESS_HOURS):
            raise ValueError(f"access_hours must be between 1 and {MAX_ACCESS_HOURS}")
        if self.kis_role == "custom" and self.custom_role_id is None:
            raise ValueError("custom_role_id required when kis_role is 'custom'")
        if self.kis_role is not None and self.kis_role != "custom":
            self.custom_role_id = None
        return self


@router.post("/access-codes")
def create_access_code(
    payload: CreateCodePayload,
    admin: dict = Depends(_require),
    locale: str = Depends(get_locale),
):
    _require_feature(locale)

    if payload.kis_role == "custom" and database.get_custom_role(payload.custom_role_id) is None:
        raise HTTPException(status_code=400, detail=t("access.invalidCustomRole", locale))

    if payload.kis_role == "custom":
        role_row = database.get_custom_role(payload.custom_role_id)
        granted = role_row["permissions"] if role_row else []
    else:
        granted = SYSTEM_ROLE_PERMISSIONS.get(payload.kis_role, ())
    assert_may_grant(permissions_of(admin), granted, locale)

    code = new_code()
    valid_until = datetime.now() + timedelta(days=payload.valid_days)
    code_id = repo.create_code(
        code=code,
        label=payload.label,
        role=payload.kis_role,
        custom_role_id=payload.custom_role_id,
        max_uses=payload.max_uses,
        valid_until=valid_until,
        access_hours=payload.access_hours,
        show_credentials=payload.show_credentials,
        show_evaluation=payload.show_evaluation,
        created_by=admin.get("user_id", 0),
    )
    return {
        "id": code_id,
        "code": code,
        "label": payload.label,
        "max_uses": payload.max_uses,
        "valid_until": valid_until,
        "access_hours": payload.access_hours,
        "show_credentials": payload.show_credentials,
        "show_evaluation": payload.show_evaluation,
    }


@router.get("/access-codes")
def list_access_codes(admin: dict = Depends(_require), locale: str = Depends(get_locale)):
    _require_feature(locale)
    jetzt = datetime.now()
    return {
        "codes": [
            {
                **{schluessel: eintrag[schluessel] for schluessel in (
                    "id", "code", "label", "role", "custom_role_id", "max_uses",
                    "used_count", "valid_until", "access_hours", "show_credentials",
                    "show_evaluation", "active", "created_at",
                )},
                "status": status_of(
                    active=eintrag["active"],
                    used_count=eintrag["used_count"],
                    max_uses=eintrag["max_uses"],
                    valid_until=eintrag["valid_until"],
                    now=jetzt,
                ),
            }
            for eintrag in repo.list_codes()
        ]
    }


@router.patch("/access-codes/{code_id}")
def patch_access_code(
    code_id: int,
    payload: PatchCodePayload,
    admin: dict = Depends(_require),
    locale: str = Depends(get_locale),
):
    _require_feature(locale)

    if payload.active is not None:
        if not repo.set_active(code_id, payload.active):
            raise HTTPException(status_code=404, detail=t("access.notFound", locale))

    if payload.label is not None:
        if repo.get_code_by_id(code_id) is None:
            raise HTTPException(status_code=404, detail=t("access.notFound", locale))

        if payload.kis_role == "custom" and database.get_custom_role(payload.custom_role_id) is None:
            raise HTTPException(status_code=400, detail=t("access.invalidCustomRole", locale))

        if payload.kis_role == "custom":
            role_row = database.get_custom_role(payload.custom_role_id)
            granted = role_row["permissions"] if role_row else []
        else:
            granted = SYSTEM_ROLE_PERMISSIONS.get(payload.kis_role, ())
        assert_may_grant(permissions_of(admin), granted, locale)

        valid_until = datetime.now() + timedelta(days=payload.valid_days)
        if not repo.update_code(
            code_id,
            label=payload.label,
            role=payload.kis_role,
            custom_role_id=payload.custom_role_id,
            max_uses=payload.max_uses,
            valid_until=valid_until,
            access_hours=payload.access_hours,
            show_credentials=payload.show_credentials,
            show_evaluation=payload.show_evaluation,
        ):
            raise HTTPException(status_code=400, detail=t("access.maxUsesBelowUsed", locale))

    return {"status": "ok"}


@router.delete("/access-codes/{code_id}")
def delete_access_code(
    code_id: int,
    admin: dict = Depends(_require),
    locale: str = Depends(get_locale),
):
    """Removes only the code, every account it created stays."""
    _require_feature(locale)
    if not repo.delete_code(code_id):
        raise HTTPException(status_code=404, detail=t("access.notFound", locale))
    return {"status": "ok"}


@router.get("/access-codes/{code_id}/users")
def list_access_code_users(
    code_id: int,
    admin: dict = Depends(_require),
    locale: str = Depends(get_locale),
):
    _require_feature(locale)
    jetzt = datetime.now()
    return {
        "users": [
            {
                **eintrag,
                "status": user_status_of(
                    active=eintrag["active"],
                    access_expires_at=eintrag["access_expires_at"],
                    now=jetzt,
                ),
            }
            for eintrag in repo.list_users_for_code(code_id)
        ]
    }


@router.post("/access-codes/users/{user_id}/password")
def reset_access_code_user_password(
    user_id: int,
    admin: dict = Depends(_require),
    locale: str = Depends(get_locale),
):
    """Gives an account made from a code a brand new password, never a real staff or admin account."""
    _require_feature(locale)
    konto = database.get_user_by_id(user_id)
    if not konto or not konto.get("access_code_id"):
        raise HTTPException(status_code=403, detail=t("access.notFromCode", locale))

    password = generate_password()
    try:
        database.set_user_password(user_id, hash_password(password))
    except Exception as e:
        logger.error("password reset failed for user_id={}: {}", user_id, e)
        raise HTTPException(status_code=500, detail=t("access.passwordResetFailed", locale))

    logger.info("admin {} reset the password for user_id={}", admin.get("email"), user_id)
    return {"username": konto["ldap_username"], "password": password}


@router.get("/access-codes/users/{user_id}/activity")
def access_code_user_activity(
    user_id: int,
    admin: dict = Depends(_require),
    locale: str = Depends(get_locale),
):
    """Read-only look at a test account's modules and chat history, never for a real account."""
    _require_feature(locale)
    konto = database.get_user_by_id(user_id)
    if not konto or not konto.get("access_code_id"):
        raise HTTPException(status_code=403, detail=t("access.notFromCode", locale))

    return {
        "workspaces": repo.list_workspaces_for_user(user_id),
        "messages": repo.list_messages_for_user(user_id),
    }
