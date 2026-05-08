# backend/tests/test_permissions.py
from src.permissions import (
    SYSTEM_ROLES,
    ALL_TOOL_KEYS,
    permissions_for_system_role,
)


def test_system_roles_constant_lists_three_fixed_roles():
    assert SYSTEM_ROLES == ("admin", "staff", "user")


def test_admin_has_all_permissions():
    perms = permissions_for_system_role("admin")
    assert perms.allow_admin_panel is True
    assert perms.allow_aia is True
    assert set(perms.tools) == set(ALL_TOOL_KEYS)


def test_staff_has_everything_except_admin_panel():
    perms = permissions_for_system_role("staff")
    assert perms.allow_admin_panel is False
    assert perms.allow_aia is True
    assert set(perms.tools) == set(ALL_TOOL_KEYS)


def test_user_has_only_aia_workspace_access_no_create():
    perms = permissions_for_system_role("user")
    assert perms.allow_admin_panel is False
    assert perms.allow_aia is True   # can OPEN assigned workspaces
    assert perms.allow_workspace_create is False
    assert perms.tools == ()


def test_unknown_role_raises():
    import pytest
    with pytest.raises(ValueError):
        permissions_for_system_role("ninja")
