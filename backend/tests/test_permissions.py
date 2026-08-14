# backend/tests/test_permissions.py
import pytest

from src.permissions import (
    SYSTEM_ROLES,
    custom_role_permissions,
    permissions_for_system_role,
    resolve_user_permissions,
)
from src.permissions_registry import (
    ALL_PERMISSION_KEYS,
    PERM_AIA_USE,
    PERM_AIA_WORKSPACE_CREATE,
    PERM_SET_AIA_LEVEL,
    PERM_SET_SYSTEM,
    PERM_SET_USERS_ALL,
    SETTING_FIELD_PERMISSIONS,
    keys_from_legacy,
    valid_keys,
)
from src.tools_registry import ALL_TOOL_KEYS


# ── Der Katalog ───────────────────────────────────────────────────────────────

def test_catalog_has_no_duplicates():
    assert len(ALL_PERMISSION_KEYS) == len(set(ALL_PERMISSION_KEYS))


def test_every_tool_has_a_permission():
    for tool in ALL_TOOL_KEYS:
        assert f"tools.{tool}" in ALL_PERMISSION_KEYS


def test_valid_keys_drops_unknown_and_orders_by_catalog():
    out = valid_keys([PERM_SET_SYSTEM, "erfundenes.recht", PERM_AIA_USE, PERM_AIA_USE])
    assert out == (PERM_AIA_USE, PERM_SET_SYSTEM)


def test_every_settings_field_points_at_a_known_permission():
    for field, key in SETTING_FIELD_PERMISSIONS.items():
        assert key in ALL_PERMISSION_KEYS, field


# ── Systemrollen behalten ihre bisherigen Rechte ──────────────────────────────

def test_system_roles_constant_lists_three_fixed_roles():
    assert SYSTEM_ROLES == ("admin", "staff", "user")


def test_admin_has_all_permissions():
    perms = permissions_for_system_role("admin")
    assert perms.allow_admin_panel is True
    assert perms.allow_aia is True
    assert set(perms.tools) == set(ALL_TOOL_KEYS)
    assert set(perms.keys) == set(ALL_PERMISSION_KEYS)


def test_staff_has_everything_except_admin_panel():
    perms = permissions_for_system_role("staff")
    assert perms.allow_admin_panel is False
    assert perms.allow_aia is True
    assert perms.allow_workspace_create is True
    assert set(perms.tools) == set(ALL_TOOL_KEYS)


def test_user_has_only_aia_workspace_access_no_create():
    perms = permissions_for_system_role("user")
    assert perms.allow_admin_panel is False
    assert perms.allow_aia is True   # can OPEN assigned workspaces
    assert perms.allow_workspace_create is False
    assert perms.tools == ()


def test_unknown_role_raises():
    with pytest.raises(ValueError):
        permissions_for_system_role("ninja")


# ── Auflösung ─────────────────────────────────────────────────────────────────

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


# ── LDAP-Schalter ─────────────────────────────────────────────────────────────

def test_admin_has_ldap_user_create_when_flag_on(monkeypatch):
    from src.dependencies import get_settings

    monkeypatch.setenv("LDAP_USER_CREATION_ENABLED", "true")
    get_settings.cache_clear()
    try:
        perms = resolve_user_permissions(role="admin", custom_role_id=None, is_env_admin=False)
        assert perms.allow_ldap_user_create is True
    finally:
        get_settings.cache_clear()


def test_staff_does_not_get_ldap_user_create_even_with_flag(monkeypatch):
    from src.dependencies import get_settings

    monkeypatch.setenv("LDAP_USER_CREATION_ENABLED", "true")
    get_settings.cache_clear()
    try:
        perms = resolve_user_permissions(role="staff", custom_role_id=None, is_env_admin=False)
        assert perms.allow_ldap_user_create is False
    finally:
        get_settings.cache_clear()


def test_admin_no_ldap_user_create_when_flag_off(monkeypatch):
    from src.dependencies import get_settings

    monkeypatch.delenv("LDAP_USER_CREATION_ENABLED", raising=False)
    get_settings.cache_clear()
    try:
        perms = resolve_user_permissions(role="admin", custom_role_id=None, is_env_admin=False)
        assert perms.allow_ldap_user_create is False
    finally:
        get_settings.cache_clear()


def test_env_admin_gets_ldap_user_create_when_flag_on(monkeypatch):
    from src.dependencies import get_settings

    monkeypatch.setenv("LDAP_USER_CREATION_ENABLED", "true")
    get_settings.cache_clear()
    try:
        perms = resolve_user_permissions(role="user", custom_role_id=None, is_env_admin=True)
        assert perms.allow_ldap_user_create is True
    finally:
        get_settings.cache_clear()


# ── Eigene Rollen ─────────────────────────────────────────────────────────────

def test_custom_role_with_only_aia_use_reads_but_cannot_create():
    perms = custom_role_permissions([PERM_AIA_USE])
    assert perms.allow_aia is True
    assert perms.allow_workspace_create is False
    assert perms.allow_admin_panel is False
    assert perms.allow_ldap_user_create is False


def test_custom_role_with_workspace_create_gets_lecturer_view():
    perms = custom_role_permissions([PERM_AIA_USE, PERM_AIA_WORKSPACE_CREATE])
    assert perms.allow_workspace_create is True
    assert perms.allow_admin_panel is False


def test_custom_role_unknown_key_is_dropped_not_fatal():
    perms = custom_role_permissions([PERM_AIA_USE, "recht.das.es.nicht.gibt"])
    assert perms.allow_aia is True
    assert "recht.das.es.nicht.gibt" not in perms.keys


def test_custom_role_tools_are_layered_on_top():
    tool = ALL_TOOL_KEYS[0]
    perms = custom_role_permissions([PERM_AIA_USE, f"tools.{tool}"])
    assert tool in perms.tools
    assert perms.allow_workspace_create is False


# Der eigentliche Anlass des Umbaus: eine Rolle, die genau eine Seite des
# Bereichs pflegen darf und sonst nichts.
def test_custom_role_with_one_settings_key_reaches_the_area():
    perms = custom_role_permissions([PERM_AIA_USE, PERM_SET_AIA_LEVEL])
    assert perms.allow_admin_panel is True
    assert perms.has(PERM_SET_AIA_LEVEL) is True
    assert perms.has(PERM_SET_SYSTEM) is False
    assert perms.has(PERM_SET_USERS_ALL) is False
    assert perms.tools == ()


# ── Umzug der alten Spalten ───────────────────────────────────────────────────

def test_legacy_edit_role_with_tools_maps_to_four_keys():
    keys = keys_from_legacy("edit", ["translation", "tts"])
    assert set(keys) == {
        PERM_AIA_USE,
        PERM_AIA_WORKSPACE_CREATE,
        "tools.translation",
        "tools.tts",
    }


def test_legacy_read_role_loses_nothing_but_gains_no_create():
    keys = keys_from_legacy("read", [])
    assert keys == (PERM_AIA_USE,)


def test_legacy_unknown_tool_is_dropped():
    keys = keys_from_legacy("none", ["translation", "erfundenes-werkzeug"])
    assert keys == (PERM_AIA_USE, "tools.translation")
