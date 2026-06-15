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


def test_admin_has_ldap_user_create_when_flag_on(monkeypatch):
    from src.dependencies import get_settings
    from src.permissions import resolve_user_permissions

    monkeypatch.setenv("LDAP_USER_CREATION_ENABLED", "true")
    get_settings.cache_clear()
    try:
        perms = resolve_user_permissions(role="admin", custom_role_id=None, is_env_admin=False)
        assert perms.allow_ldap_user_create is True
    finally:
        get_settings.cache_clear()


def test_staff_does_not_get_ldap_user_create_even_with_flag(monkeypatch):
    from src.dependencies import get_settings
    from src.permissions import resolve_user_permissions

    monkeypatch.setenv("LDAP_USER_CREATION_ENABLED", "true")
    get_settings.cache_clear()
    try:
        perms = resolve_user_permissions(role="staff", custom_role_id=None, is_env_admin=False)
        assert perms.allow_ldap_user_create is False
    finally:
        get_settings.cache_clear()


def test_admin_no_ldap_user_create_when_flag_off(monkeypatch):
    from src.dependencies import get_settings
    from src.permissions import resolve_user_permissions

    monkeypatch.delenv("LDAP_USER_CREATION_ENABLED", raising=False)
    get_settings.cache_clear()
    try:
        perms = resolve_user_permissions(role="admin", custom_role_id=None, is_env_admin=False)
        assert perms.allow_ldap_user_create is False
    finally:
        get_settings.cache_clear()


def test_env_admin_gets_ldap_user_create_when_flag_on(monkeypatch):
    from src.dependencies import get_settings
    from src.permissions import resolve_user_permissions

    monkeypatch.setenv("LDAP_USER_CREATION_ENABLED", "true")
    get_settings.cache_clear()
    try:
        perms = resolve_user_permissions(role="user", custom_role_id=None, is_env_admin=True)
        assert perms.allow_ldap_user_create is True
    finally:
        get_settings.cache_clear()


from src.permissions import custom_role_permissions


def test_custom_role_aia_none_still_grants_link_read():
    # Link-based read access is a universal baseline: even a tools-only
    # role ('none') may follow a shared link and read an enrolled workspace.
    # It just cannot create or own workspaces.
    perms = custom_role_permissions(aia_access="none", tool_keys=[])
    assert perms.allow_aia is True
    assert perms.allow_workspace_create is False
    assert perms.allow_admin_panel is False


def test_custom_role_aia_read_grants_link_access_only():
    perms = custom_role_permissions(aia_access="read", tool_keys=[])
    assert perms.allow_aia is True
    assert perms.allow_workspace_create is False
    assert perms.allow_admin_panel is False
    assert perms.allow_ldap_user_create is False


def test_custom_role_aia_edit_grants_lecturer_view():
    perms = custom_role_permissions(aia_access="edit", tool_keys=[])
    assert perms.allow_aia is True
    assert perms.allow_workspace_create is True
    assert perms.allow_admin_panel is False
    assert perms.allow_ldap_user_create is False


def test_custom_role_unknown_aia_access_defaults_to_link_read():
    # Unknown/corrupt values degrade to the safe baseline: link read only,
    # never workspace creation.
    perms = custom_role_permissions(aia_access="ninja", tool_keys=[])
    assert perms.allow_aia is True
    assert perms.allow_workspace_create is False


def test_custom_role_tools_are_layered_on_user_base():
    valid_tool = next(iter(ALL_TOOL_KEYS))
    perms = custom_role_permissions(aia_access="read", tool_keys=[valid_tool])
    assert valid_tool in perms.tools
    assert perms.allow_workspace_create is False


def test_custom_role_edit_with_tools_combines_both():
    valid_tool = next(iter(ALL_TOOL_KEYS))
    perms = custom_role_permissions(aia_access="edit", tool_keys=[valid_tool])
    assert perms.allow_workspace_create is True
    assert valid_tool in perms.tools
