"""Admin routes for the permission table, every checkbox is its own request."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src import database as db
from src.dependencies_rbac import assert_may_grant, permissions_of, require_permission
from src.features.admin.repository.roles import RoleNameTaken
from src.i18n import get_locale, t
from src.permissions_registry import (
    ALL_PERMISSION_KEYS,
    GROUP_CHAPTER,
    GROUPS,
    PERMISSION_GROUPS,
    PERM_SET_USERS_ROLES,
    SYSTEM_ROLE_PERMISSIONS,
    SYSTEM_ROLES,
    valid_keys,
)

router = APIRouter(tags=["admin: roles"])

# Whoever hands out permissions needs the right to do so.
_require = require_permission(PERM_SET_USERS_ROLES)


class RolePayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    permissions: list[str] = Field(default_factory=list)


class RoleNamePayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)


class PermissionTogglePayload(BaseModel):
    key: str
    granted: bool


@router.get("/roles")
async def list_roles(admin=Depends(_require)):
    """Rows, columns and checkboxes of the permission table in one call."""
    perms = permissions_of(admin)
    return {
        "groups": [
            {
                "key": g,
                "chapter": GROUP_CHAPTER[g],
                "permissions": list(PERMISSION_GROUPS[g]),
            }
            for g in GROUPS
        ],
        "system_roles": [
            {"key": r, "permissions": list(SYSTEM_ROLE_PERMISSIONS[r])}
            for r in SYSTEM_ROLES
        ],
        "custom_roles": db.list_custom_roles(),
        # What the caller does not hold themselves the table shows locked.
        "grantable": list(perms.keys & set(ALL_PERMISSION_KEYS)),
    }


@router.post("/roles")
async def create_role(
    payload: RolePayload,
    admin=Depends(_require),
    locale: str = Depends(get_locale),
):
    keys = valid_keys(payload.permissions)
    assert_may_grant(permissions_of(admin), keys, locale)
    name = payload.name.strip()
    try:
        new_id = db.create_custom_role(name, list(keys))
    except RoleNameTaken:
        raise HTTPException(
            status_code=409, detail=t("admin.role.nameTaken", locale, name=name)
        )
    return db.get_custom_role(new_id)


@router.patch("/roles/{role_id}")
async def rename_role(
    role_id: int,
    payload: RoleNamePayload,
    _admin=Depends(_require),
    locale: str = Depends(get_locale),
):
    """Rename only, the checkboxes go through their own endpoint."""
    if db.get_custom_role(role_id) is None:
        raise HTTPException(status_code=404, detail="Role not found")
    name = payload.name.strip()
    try:
        db.rename_custom_role(role_id, name)
    except RoleNameTaken:
        raise HTTPException(
            status_code=409, detail=t("admin.role.nameTaken", locale, name=name)
        )
    return db.get_custom_role(role_id)


@router.patch("/roles/{role_id}/permissions")
async def toggle_role_permission(
    role_id: int,
    payload: PermissionTogglePayload,
    admin=Depends(_require),
    locale: str = Depends(get_locale),
):
    """Sets or clears a checkbox, you may only grant what you hold yourself."""
    if payload.key not in ALL_PERMISSION_KEYS:
        raise HTTPException(status_code=400, detail=f"Unknown permission: {payload.key}")
    if db.get_custom_role(role_id) is None:
        raise HTTPException(status_code=404, detail="Role not found")
    if payload.granted:
        assert_may_grant(permissions_of(admin), [payload.key], locale)
    try:
        permissions = db.set_custom_role_permission(role_id, payload.key, payload.granted)
    except LookupError:
        raise HTTPException(status_code=404, detail="Role not found")
    return {"id": role_id, "permissions": permissions}


@router.delete("/roles/{role_id}")
async def delete_role(
    role_id: int,
    admin=Depends(_require),
    locale: str = Depends(get_locale),
):
    role = db.get_custom_role(role_id)
    if role is None:
        raise HTTPException(status_code=404, detail="Role not found")
    # Whoever could not grant a role may not dissolve it either.
    assert_may_grant(permissions_of(admin), role["permissions"], locale)
    db.delete_custom_role(role_id)
    return {"status": "ok"}
