"""FastAPI dependencies enforcing RBAC. Use these to gate routes."""
from fastapi import Depends, HTTPException, Request

from src.dependencies import get_current_user, get_settings
from src.i18n import get_locale, t
from src.permissions import Permissions, resolve_user_permissions


def _is_env_admin(email: str | None) -> bool:
    settings = get_settings()
    if not email or not settings.admin_email:
        return False
    return email.lower() == settings.admin_email.lower()


async def get_user_permissions(request: Request) -> Permissions:
    user = await get_current_user(request)
    role = user.get("role", "user")
    custom_role_id = user.get("custom_role_id")
    is_env_admin = _is_env_admin(user.get("email"))
    return resolve_user_permissions(role, custom_role_id, is_env_admin)


async def require_admin(
    perms: Permissions = Depends(get_user_permissions),
    locale: str = Depends(get_locale),
) -> Permissions:
    if not perms.allow_admin_panel:
        raise HTTPException(status_code=403, detail=t("auth.adminRequired", locale))
    return perms


async def require_aia_access(
    perms: Permissions = Depends(get_user_permissions),
    locale: str = Depends(get_locale),
) -> Permissions:
    if not perms.allow_aia:
        raise HTTPException(status_code=403, detail=t("auth.aiaForbidden", locale))
    return perms


async def require_workspace_create(
    perms: Permissions = Depends(get_user_permissions),
    locale: str = Depends(get_locale),
) -> Permissions:
    if not perms.allow_workspace_create:
        raise HTTPException(status_code=403, detail=t("auth.workspaceCreateForbidden", locale))
    return perms


def require_tool_access(tool_key: str):
    """Factory for a dependency that checks tool access for a named tool key.

    Usage:
        @router.post("/translate", dependencies=[Depends(require_tool_access("translation"))])
    """
    async def _check(
        perms: Permissions = Depends(get_user_permissions),
        locale: str = Depends(get_locale),
    ) -> Permissions:
        if tool_key not in perms.tools:
            raise HTTPException(status_code=403, detail=t("auth.toolForbidden", locale))
        return perms
    return _check
