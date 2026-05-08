# backend/src/permissions.py
"""Permission model for RBAC.

System roles (admin/staff/user) have HARDCODED permissions defined here.
Custom roles store their permissions in the `custom_roles` DB table.
"""
from dataclasses import dataclass

from src.tools_registry import ALL_TOOL_KEYS

SYSTEM_ROLES: tuple[str, ...] = ("admin", "staff", "user")


@dataclass(frozen=True)
class Permissions:
    allow_admin_panel: bool
    allow_aia: bool                 # may open AIA workspaces assigned to them
    allow_workspace_create: bool    # may create new AIA workspaces
    tools: tuple[str, ...]          # tool keys the user may use


def permissions_for_system_role(role: str) -> Permissions:
    if role == "admin":
        return Permissions(
            allow_admin_panel=True,
            allow_aia=True,
            allow_workspace_create=True,
            tools=tuple(ALL_TOOL_KEYS),
        )
    if role == "staff":
        return Permissions(
            allow_admin_panel=False,
            allow_aia=True,
            allow_workspace_create=True,
            tools=tuple(ALL_TOOL_KEYS),
        )
    if role == "user":
        return Permissions(
            allow_admin_panel=False,
            allow_aia=True,                # can OPEN assigned workspaces
            allow_workspace_create=False,  # but not create
            tools=(),
        )
    raise ValueError(f"Unknown system role: {role!r}")


def resolve_user_permissions(
    role: str,
    custom_role_id: int | None,
    is_env_admin: bool,
) -> Permissions:
    """Compute effective permissions for a session.

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
        return custom_role_permissions(cr["allow_aia"], cr["allowed_tools"])
    # Unknown / corrupt role -> safest fallback
    return permissions_for_system_role("user")


def custom_role_permissions(allow_aia: bool, tool_keys: list[str]) -> Permissions:
    """Permissions for a DB-backed custom role.

    Custom roles never grant admin or workspace-create rights.
    """
    valid_tools = tuple(k for k in tool_keys if k in ALL_TOOL_KEYS)
    return Permissions(
        allow_admin_panel=False,
        allow_aia=allow_aia,
        allow_workspace_create=False,
        tools=valid_tools,
    )
