"""Admin endpoint to create new LDAP users (temporary — replaced by SSO)."""
from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel, Field

from src.dependencies import get_admin_user, get_settings
from src.i18n import get_locale, t
from src.ldap_admin import (
    LdapServiceError,
    LdapUserExistsError,
    LdapValidationError,
    create_ldap_user,
)

router = APIRouter(tags=["admin: ldap-users"])


class CreateLdapUserPayload(BaseModel):
    uid: str = Field(..., min_length=2, max_length=32)
    given_name: str = Field(..., min_length=1, max_length=64)
    surname: str = Field(..., min_length=1, max_length=64)
    email: str = Field(..., min_length=3, max_length=128)
    employee_type: str = Field(..., pattern="^(staff|student)$")


@router.post("/ldap-users")
async def admin_create_ldap_user(
    payload: CreateLdapUserPayload,
    admin: dict = Depends(get_admin_user),
    locale: str = Depends(get_locale),
):
    settings = get_settings()
    if not settings.ldap_user_creation_enabled:
        raise HTTPException(status_code=404, detail=t("admin.ldap.featureDisabled", locale))

    try:
        password = create_ldap_user(
            settings=settings,
            uid=payload.uid,
            given_name=payload.given_name,
            surname=payload.surname,
            email=payload.email,
            employee_type=payload.employee_type,
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

    logger.info("admin {} created LDAP user uid={}", admin.get("email"), payload.uid)
    return {"uid": payload.uid, "generated_password": password}
