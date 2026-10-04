"""Der Rechte-Katalog richtet sich nach dem Modul-Profil."""
from src.modules import MODULE_AIA, MODULE_TOOLS
from src.permissions import custom_role_permissions, is_full_admin, permissions_for_system_role
from src.permissions_registry import (
    ALL_PERMISSION_KEYS,
    PERM_AIA_USE,
    PERM_AIA_WORKSPACE_CREATE,
    PERM_SET_AIA_LEVEL,
    PERM_SET_AIA_SOURCES,
    PERM_SET_AIA_USAGE,
    PERM_SET_EVENT,
    PERM_SET_PROVIDERS,
    PERM_SET_SYSTEM,
    PERM_SET_TOOLS_JOBS,
    PERM_SET_TOOLS_LIMITS,
    PERM_SET_TOOLS_RELEASE,
    PERM_SET_TOOLS_STATS,
    PERM_SET_USERS_ROLES,
    keys_for_modules,
    matrix_layout_for,
)

BEIDE = frozenset({MODULE_AIA, MODULE_TOOLS})
NUR_AIA = frozenset({MODULE_AIA})
NUR_TOOLS = frozenset({MODULE_TOOLS})


def test_beide_module_geben_den_vollen_katalog():
    assert keys_for_modules(BEIDE) == ALL_PERMISSION_KEYS


def test_ohne_tools_fallen_die_werkzeug_rechte_weg():
    keys = keys_for_modules(NUR_AIA)
    assert not [k for k in keys if k.startswith("tools.")]


def test_ohne_tools_fallen_auch_die_verwalten_rechte_weg():
    keys = keys_for_modules(NUR_AIA)
    assert PERM_SET_TOOLS_RELEASE not in keys
    assert PERM_SET_TOOLS_JOBS not in keys
    assert PERM_SET_TOOLS_LIMITS not in keys
    assert PERM_SET_TOOLS_STATS not in keys


def test_ohne_tools_bleiben_die_assistenten_rechte():
    keys = keys_for_modules(NUR_AIA)
    assert PERM_AIA_USE in keys
    assert PERM_AIA_WORKSPACE_CREATE in keys
    assert PERM_SET_AIA_SOURCES in keys
    assert PERM_SET_AIA_USAGE in keys


def test_ohne_aia_fallen_die_assistenten_rechte_weg():
    keys = keys_for_modules(NUR_TOOLS)
    assert PERM_AIA_USE not in keys
    assert PERM_AIA_WORKSPACE_CREATE not in keys
    assert PERM_SET_AIA_SOURCES not in keys
    assert PERM_SET_AIA_LEVEL not in keys
    assert PERM_SET_AIA_USAGE not in keys


def test_ohne_aia_bleiben_die_werkzeug_rechte():
    keys = keys_for_modules(NUR_TOOLS)
    assert PERM_SET_TOOLS_RELEASE in keys
    assert "tools.tts" in keys


def test_gemeinsame_rechte_bleiben_in_jedem_profil():
    for profil in (BEIDE, NUR_AIA, NUR_TOOLS):
        keys = keys_for_modules(profil)
        assert PERM_SET_SYSTEM in keys
        assert PERM_SET_PROVIDERS in keys
        assert PERM_SET_USERS_ROLES in keys


def test_katalog_reihenfolge_bleibt_erhalten():
    keys = keys_for_modules(NUR_AIA)
    stellen = [ALL_PERMISSION_KEYS.index(k) for k in keys]
    assert stellen == sorted(stellen)


def test_matrix_verliert_die_leer_gewordene_gruppe():
    gruppen = [g for _, g, _ in matrix_layout_for(NUR_AIA)]
    assert "tools" not in gruppen
    assert "set.werkzeuge" not in gruppen
    assert "aia" in gruppen


def test_matrix_behaelt_die_gemischte_statistik_gruppe():
    layout = {g: keys for _, g, keys in matrix_layout_for(NUR_AIA)}
    assert PERM_SET_TOOLS_STATS not in layout["set.statistik"]
    assert PERM_SET_AIA_USAGE in layout["set.statistik"]


def test_matrix_mit_beiden_modulen_ist_unveraendert():
    from src.permissions_registry import MATRIX_LAYOUT
    assert matrix_layout_for(BEIDE) == MATRIX_LAYOUT


def test_systemrolle_verliert_die_werkzeuge_ohne_das_modul():
    perms = permissions_for_system_role("staff", modules=NUR_AIA)
    assert perms.tools == ()
    assert perms.allow_aia is True


def test_systemrolle_verliert_den_assistenten_ohne_das_modul():
    perms = permissions_for_system_role("staff", modules=NUR_TOOLS)
    assert perms.allow_aia is False
    assert perms.allow_workspace_create is False
    assert "tts" in perms.tools


def test_admin_verliert_die_rechte_des_abgeschalteten_moduls():
    perms = permissions_for_system_role("admin", modules=NUR_TOOLS)
    assert PERM_SET_AIA_SOURCES not in perms.keys
    assert PERM_SET_TOOLS_RELEASE in perms.keys


def test_admin_behaelt_den_verwaltungsbereich_ohne_assistent():
    perms = permissions_for_system_role("admin", modules=NUR_TOOLS)
    assert perms.allow_admin_panel is True


def test_eigene_rolle_verliert_die_rechte_des_abgeschalteten_moduls():
    perms = custom_role_permissions(
        [PERM_AIA_USE, "tools.tts", PERM_SET_SYSTEM], modules=NUR_TOOLS
    )
    assert PERM_AIA_USE not in perms.keys
    assert "tts" in perms.tools
    assert PERM_SET_SYSTEM in perms.keys


def test_eigene_rolle_ohne_uebrige_rechte_ist_leer_statt_kaputt():
    perms = custom_role_permissions([PERM_AIA_USE], modules=NUR_TOOLS)
    assert perms.keys == frozenset()
    assert perms.allow_admin_panel is False


# --- voller Admin ---------------------------------------------------------------

def test_voller_admin_haelt_jede_verwalten_seite_seines_profils():
    assert is_full_admin(permissions_for_system_role("admin", BEIDE), BEIDE) is True
    assert is_full_admin(permissions_for_system_role("admin", NUR_AIA), NUR_AIA) is True


def test_wer_nur_eine_verwalten_seite_hat_ist_kein_voller_admin():
    assert is_full_admin(custom_role_permissions([PERM_SET_EVENT], BEIDE), BEIDE) is False
    assert is_full_admin(permissions_for_system_role("staff", BEIDE), BEIDE) is False
