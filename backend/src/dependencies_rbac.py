"""FastAPI dependencies enforcing RBAC. Use these to gate routes."""
from fastapi import Depends, HTTPException, Request

from src.dependencies import get_current_user, get_settings
from src.i18n import get_locale, t
from src.permissions import Permissions, resolve_user_permissions
from src.permissions_registry import is_settings_key


def _is_env_admin(email: str | None) -> bool:
    settings = get_settings()
    if not email or not settings.admin_email:
        return False
    return email.lower() == settings.admin_email.lower()


def permissions_of(user: dict) -> Permissions:
    """Rechte zu einem bereits geladenen Nutzer-Woerterbuch."""
    return resolve_user_permissions(
        user.get("role", "user"),
        user.get("custom_role_id"),
        _is_env_admin(user.get("email")),
    )


async def get_user_permissions(request: Request) -> Permissions:
    return permissions_of(await get_current_user(request))


def require_permission(*keys: str):
    """Torwaechter fuer eine Route, die eines der genannten Rechte verlangt.

    Liefert das Nutzer-Woerterbuch zurueck und ist damit ein direkter Ersatz fuer
    ``get_admin_user``: Routen, die den Admin selbst brauchen (etwa fuer die
    eigene Adresse), bekommen ihn weiter.

    Mehrere Schluessel bedeuten ODER. Das braucht die Auslastungskarte, die auf
    zwei Seiten steht.

    Usage:
        @router.get("/stats", dependencies=[Depends(require_permission(PERM_SET_TOOLS_STATS))])
    """
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
    """Fuer Routen, die jede Seite des Bereichs beim Aufbau braucht.

    Die Einstellungen kommen in einem Datensatz, den jede Seite liest. Lesen ist
    deshalb fuer alle offen, die irgendeine Seite sehen duerfen. Gespeichert wird
    dagegen Feld fuer Feld geprueft, siehe ``routes/admin/settings.py``.
    """
    if not any(is_settings_key(k) for k in permissions_of(user).keys):
        raise HTTPException(
            status_code=403, detail=t("auth.permissionRequired", locale)
        )
    return user


def assert_may_grant(actor: Permissions, keys, locale: str) -> None:
    """Man kann nur vergeben, was man selbst hat.

    Ohne diese Regel waere jedes Recht, das Rollen oder Nutzer verwaltet, ein
    Weg zum Administrator: eine Rolle mit ``settings.system`` bauen und sie sich
    selbst zuweisen. Der Administrator hat alles und merkt von der Regel nichts.
    """
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
