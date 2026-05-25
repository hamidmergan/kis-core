# backend/src/permissions.py
"""Permission model for RBAC.

System roles (admin/staff/user) have HARDCODED permissions defined here.
Custom roles store their permissions in the `custom_roles` DB table.
"""
from dataclasses import dataclass

from src.dependencies import get_settings
from src.tools_registry import ALL_TOOL_KEYS

SYSTEM_ROLES: tuple[str, ...] = ("admin", "staff", "user")


@dataclass(frozen=True)
class Permissions:
    allow_admin_panel: bool
    allow_aia: bool                 # may open AIA workspaces assigned to them
    allow_workspace_create: bool    # may create new AIA workspaces
    allow_ldap_user_create: bool    # admin-only, additionally gated by env flag
    tools: tuple[str, ...]          # tool keys the user may use


def permissions_for_system_role(role: str) -> Permissions:
    if role == "admin":
        return Permissions(
            allow_admin_panel=True,
            allow_aia=True,
            allow_workspace_create=True,
            allow_ldap_user_create=False,  # gated below by env flag
            tools=tuple(ALL_TOOL_KEYS),
        )
    if role == "staff":
        return Permissions(
            allow_admin_panel=False,
            allow_aia=True,
            allow_workspace_create=True,
            allow_ldap_user_create=False,
            tools=tuple(ALL_TOOL_KEYS),
        )
    if role == "user":
        return Permissions(
            allow_admin_panel=False,
            allow_aia=True,                # can OPEN assigned workspaces
            allow_workspace_create=False,  # but not create
            allow_ldap_user_create=False,
            tools=(),
        )
    raise ValueError(f"Unknown system role: {role!r}")


def resolve_user_permissions(
    role: str,
    custom_role_id: int | None,
    is_env_admin: bool,
) -> Permissions:
    """Compute effective permissions, layering the LDAP feature flag on admins.

    Note: `get_settings()` is `lru_cache`d, so `ldap_user_creation_enabled`
    is read once per process and frozen. Toggling the env var requires a
    backend restart — matches the deploy-time-only flag strategy in the spec.
    """
    base = _resolve_base_permissions(role, custom_role_id, is_env_admin)
    if base.allow_admin_panel:
        if get_settings().ldap_user_creation_enabled:
            return Permissions(
                allow_admin_panel=base.allow_admin_panel,
                allow_aia=base.allow_aia,
                allow_workspace_create=base.allow_workspace_create,
                allow_ldap_user_create=True,
                tools=base.tools,
            )
    return base


def _resolve_base_permissions(
    role: str,
    custom_role_id: int | None,
    is_env_admin: bool,
) -> Permissions:
    """Compute base permissions before the LDAP env-flag layer.

    env-admin always wins (bootstrap super-admin). Otherwise: system role
    constants, or DB-backed custom role.
    """
    if is_env_admin:
        return permissions_for_system_role("admin")
    if role in SYSTEM_ROLES:
        return permissions_for_system_role(role)
    if role == "custom" and custom_role_id is not None:
        # Lazy import to avoid pulling psycopg2 at module import time.
        from src import database
        cr = database.get_custom_role(custom_role_id)
        if cr is None:
            # Custom role was deleted concurrently; degrade gracefully to 'user'.
            return permissions_for_system_role("user")
        return custom_role_permissions(cr["aia_access"], cr["allowed_tools"])
    # Unknown / corrupt role -> safest fallback
    return permissions_for_system_role("user")


def custom_role_permissions(aia_access: str, tool_keys: list[str]) -> Permissions:
    """Permissions for a DB-backed custom role.

    Custom roles never grant admin panel or LDAP-user-create. `aia_access`
    controls the workspace dimension independently of the user base:
      'none' -> no AIA, tools-only role
      'read' -> link access to assigned workspaces (student view)
      'edit' -> lecturer view: create + manage workspaces (staff-level AIA)
    `tool_keys` adds global tool access on top.
    """
    valid_tools = tuple(k for k in tool_keys if k in ALL_TOOL_KEYS)
    is_edit = aia_access == "edit"
    return Permissions(
        allow_admin_panel=False,
        allow_aia=aia_access in ("read", "edit"),
        allow_workspace_create=is_edit,
        allow_ldap_user_create=False,
        tools=valid_tools,
    )
