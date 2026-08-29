"""FastAPI dependencies enforcing RBAC. Use these to gate routes."""
from fastapi import Depends, HTTPException, Request

from src.dependencies import get_current_user, get_settings
from src.i18n import get_locale, t
from src.permissions import Permissions, resolve_user_permissions
from src.permissions_registry import is_settings_key
from src.services.tool_release import is_released_now


def _is_env_admin(email: str | None) -> bool:
    settings = get_settings()
    if not email or not settings.admin_email:
        return False
    return email.lower() == settings.admin_email.lower()


def permissions_of(user: dict) -> Permissions:
    """Permissions for an already loaded user dict."""
    return resolve_user_permissions(
        user.get("role", "user"),
        user.get("custom_role_id"),
        _is_env_admin(user.get("email")),
    )


async def get_user_permissions(request: Request) -> Permissions:
    return permissions_of(await get_current_user(request))


def require_permission(*keys: str):
    """Gatekeeper for a route that demands one of the named permissions."""
    async def _check(
        user: dict = Depends(get_current_user),
        locale: str = Depends(get_locale),
    ) -> dict:
        if not permissions_of(user).has(*keys):
            raise HTTPException(
                status_code=403, detail=t("auth.permissionRequired", locale)
            )
        return user
    return _check


async def require_any_settings(
    user: dict = Depends(get_current_user),
    locale: str = Depends(get_locale),
) -> dict:
    """Reading is open to everyone who may see any page of the area."""
    if not any(is_settings_key(k) for k in permissions_of(user).keys):
        raise HTTPException(
            status_code=403, detail=t("auth.permissionRequired", locale)
        )
    return user


def assert_may_grant(actor: Permissions, keys, locale: str) -> None:
    """You can only grant what you hold yourself."""
    beyond = [k for k in keys if k not in actor.keys]
    if beyond:
        raise HTTPException(status_code=403, detail=t("auth.grantBeyondOwn", locale))


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
    """Builds a dependency that checks access to a named tool."""
    async def _check(
        perms: Permissions = Depends(get_user_permissions),
        locale: str = Depends(get_locale),
    ) -> Permissions:
        if tool_key not in perms.tools or not is_released_now(tool_key):
            raise HTTPException(status_code=403, detail=t("auth.toolForbidden", locale))
        return perms
    return _check
