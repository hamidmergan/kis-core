"""Create, list, switch off and delete access codes for test rounds."""
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator

from src import database
from src.dependencies import get_settings
from src.dependencies_rbac import assert_may_grant, permissions_of, require_permission
from src.features.access_codes import repository as repo
from src.features.access_codes.service import new_code, status_of
from src.i18n import get_locale, t
from src.permissions_registry import PERM_SET_USERS_ALL, SYSTEM_ROLE_PERMISSIONS

router = APIRouter(tags=["admin: access codes"])

_require = require_permission(PERM_SET_USERS_ALL)

MAX_VALID_DAYS = 60
MAX_ACCESS_DAYS = 30
MAX_SEATS = 100


def _require_feature(locale: str) -> None:
    """Access codes hang off the same switch as creating LDAP users."""
    if not get_settings().ldap_user_creation_enabled:
        raise HTTPException(status_code=404, detail=t("access.featureDisabled", locale))


class CreateCodePayload(BaseModel):
    label: str = Field(..., min_length=1, max_length=64)
    max_uses: int = Field(50, ge=1, le=MAX_SEATS)
    valid_days: int = Field(30, ge=1, le=MAX_VALID_DAYS)
    access_days: int = Field(14, ge=1, le=MAX_ACCESS_DAYS)
    kis_role: str = Field("user", pattern="^(staff|user|custom)$")
    custom_role_id: int | None = None

    @model_validator(mode="after")
    def _label_and_role(self):
        if not self.label.strip():
            raise ValueError("label must not be blank")
        self.label = self.label.strip()
        if self.kis_role == "custom" and self.custom_role_id is None:
            raise ValueError("custom_role_id required when kis_role is 'custom'")
        if self.kis_role != "custom":
            self.custom_role_id = None
        return self


class PatchCodePayload(BaseModel):
    active: bool


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
        access_days=payload.access_days,
        created_by=admin.get("user_id", 0),
    )
    return {
        "id": code_id,
        "code": code,
        "label": payload.label,
        "max_uses": payload.max_uses,
        "valid_until": valid_until,
        "access_days": payload.access_days,
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
                    "used_count", "valid_until", "access_days", "active", "created_at",
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
    if not repo.set_active(code_id, payload.active):
        raise HTTPException(status_code=404, detail=t("access.notFound", locale))
    return {"status": "ok", "active": payload.active}


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
