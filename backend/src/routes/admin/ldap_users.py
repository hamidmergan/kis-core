"""Admin endpoint to create new LDAP users (temporary — replaced by SSO)."""
from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, Field, model_validator

from src import database
from src.dependencies import get_settings
from src.i18n import get_locale, t
from src.ldap_admin import (
    LdapServiceError,
    LdapUserExistsError,
    LdapValidationError,
    create_ldap_user,
)

from src.dependencies_rbac import require_permission
from src.permissions_registry import PERM_SET_USERS_ALL

router = APIRouter(tags=["admin: ldap-users"])

# Creating users belongs to all users, on top of the server switch.
_require = require_permission(PERM_SET_USERS_ALL)


class CreateLdapUserPayload(BaseModel):
    uid: str = Field(..., min_length=2, max_length=32)
    given_name: str = Field(..., min_length=1, max_length=64)
    surname: str = Field(..., min_length=1, max_length=64)
    email: str = Field(..., min_length=3, max_length=128)
    kis_role: str = Field(..., pattern="^(staff|user|custom)$")
    custom_role_id: int | None = None

    @model_validator(mode="after")
    def _custom_role_id_required_for_custom(self):
        if self.kis_role == "custom" and self.custom_role_id is None:
            raise ValueError("custom_role_id required when kis_role is 'custom'")
        if self.kis_role != "custom" and self.custom_role_id is not None:
            self.custom_role_id = None
        return self


def _employee_type_for_role(kis_role: str) -> str:
    """Maps employeeType onto 'staff' or 'user'."""
    return "staff" if kis_role == "staff" else "user"


@router.post("/ldap-users")
def admin_create_ldap_user(
    payload: CreateLdapUserPayload,
    admin: dict = Depends(_require),
    locale: str = Depends(get_locale),
):
    settings = get_settings()
    if not settings.account_creation_enabled:
        raise HTTPException(status_code=404, detail=t("admin.ldap.featureDisabled", locale))

    if payload.kis_role == "custom":
        if database.get_custom_role(payload.custom_role_id) is None:
            raise HTTPException(status_code=400, detail=t("admin.ldap.invalidCustomRole", locale))

    try:
        password = create_ldap_user(
            settings=settings,
            uid=payload.uid,
            given_name=payload.given_name,
            surname=payload.surname,
            email=payload.email,
            employee_type=_employee_type_for_role(payload.kis_role),
        )
    except LdapValidationError as e:
        key = {
            "uid": "admin.ldap.invalidUid",
            "email": "admin.ldap.invalidEmail",
            "employee_type": "admin.ldap.invalidEmployeeType",
            "given_name": "admin.ldap.nameRequired",
            "surname": "admin.ldap.nameRequired",
        }.get(e.field, "admin.ldap.addFailed")
        raise HTTPException(status_code=400, detail=t(key, locale))
    except LdapUserExistsError:
        raise HTTPException(status_code=409, detail=t("admin.ldap.userExists", locale))
    except LdapServiceError as e:
        logger.error("LDAP add failed for uid={}: {}", payload.uid, e)
        raise HTTPException(status_code=500, detail=t("admin.ldap.addFailed", locale))

    # Create row and whitelist entry up front so the role survives the first login.
    display_name = f"{payload.given_name.strip()} {payload.surname.strip()}"
    try:
        database.add_to_whitelist(payload.email)
        user_id = database.create_user(
            ldap_username=payload.uid,
            display_name=display_name,
            email=payload.email,
            active=1,
            role=payload.kis_role,
        )
        if payload.kis_role == "custom":
            database.set_user_role(user_id, "custom", payload.custom_role_id)
    except Exception as e:
        # The LDAP entry already exists, reported so the admin can adjust the role.
        logger.error(
            "DB write failed after LDAP add for uid={}: {}. Admin must assign role manually.",
            payload.uid,
            e,
        )
        raise HTTPException(status_code=500, detail=t("admin.ldap.dbWriteFailed", locale))

    logger.info(
        "admin {} created LDAP user uid={} role={}",
        admin.get("email"),
        payload.uid,
        payload.kis_role,
    )
    return {"uid": payload.uid, "generated_password": password}
