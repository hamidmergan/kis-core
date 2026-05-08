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


from src.permissions import resolve_user_permissions


def test_env_admin_overrides_any_role():
    perms = resolve_user_permissions(role="user", custom_role_id=None, is_env_admin=True)
    assert perms.allow_admin_panel is True


def test_unknown_role_falls_back_to_user():
    perms = resolve_user_permissions(role="banana", custom_role_id=None, is_env_admin=False)
    assert perms.allow_admin_panel is False
    assert perms.tools == ()


def test_custom_role_without_id_falls_back_to_user():
    perms = resolve_user_permissions(role="custom", custom_role_id=None, is_env_admin=False)
    assert perms.tools == ()
