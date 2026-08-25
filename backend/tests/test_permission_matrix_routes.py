"""Die Rechtematrix an den Stellen, an denen sie wirklich haelt.

Drei Dinge muessen stimmen, sonst ist die Tabelle Dekoration:
1. eine Rolle mit genau einem Einstellungsrecht kommt an ihre Seite und an
   keine andere,
2. der gemeinsame Speicher-Endpunkt laesst nur die Felder der eigenen Seite
   durch,
3. niemand kann ein Recht vergeben, das er selbst nicht hat.
"""

import pytest
from fastapi import HTTPException

from src.dependencies_rbac import assert_may_grant, permissions_of
from src.permissions import custom_role_permissions, permissions_for_system_role
from src.permissions_registry import (
    ALL_PERMISSION_KEYS,
    PERM_AIA_USE,
    PERM_SET_AIA_LEVEL,
    PERM_SET_SYSTEM,
    PERM_SET_USERS_ROLES,
    PERM_SET_USERS_WHITELIST,
)
from src.routes.admin import settings as admin_settings
from src.routes.admin._models import UpdateSettingsRequest

# Der Sprachexperte aus dem Anlass: KI-Assistent nutzen und die Seite
# Sprachniveau pflegen, sonst nichts.
SPRACHEXPERTE = (PERM_AIA_USE, PERM_SET_AIA_LEVEL)


# ── Der gemeinsame Speicher-Endpunkt ─────────────────────────────────────────

@pytest.fixture
def store(monkeypatch):
    data: dict[str, str] = {}
    monkeypatch.setattr(
        admin_settings.db, "get_setting", lambda key, default="": data.get(key, default)
    )
    monkeypatch.setattr(
        admin_settings.db, "set_setting", lambda key, value: data.__setitem__(key, value)
    )
    return data


@pytest.fixture
def as_sprachexperte(monkeypatch):
    """Nutzer mit eigener Rolle, deren Rechte fest verdrahtet sind."""
    from src import database

    monkeypatch.setattr(
        database,
        "get_custom_role",
        lambda role_id: {"id": role_id, "name": "Sprachexperte", "permissions": list(SPRACHEXPERTE)},
    )
    return {"role": "custom", "custom_role_id": 1, "email": "sprach@th-luebeck.de"}


async def test_sprachexperte_may_save_the_prompt(store, as_sprachexperte):
    await admin_settings.update_settings(
        UpdateSettingsRequest(language_diagnosis_prompt="Sprich einfach."),
        as_sprachexperte,
        "de",
    )
    assert store["language_diagnosis_prompt"] == "Sprich einfach."


async def test_sprachexperte_may_not_touch_a_foreign_field(store, as_sprachexperte):
    with pytest.raises(HTTPException) as err:
        await admin_settings.update_settings(
            UpdateSettingsRequest(whitelist_enabled=True), as_sprachexperte, "de"
        )
    assert err.value.status_code == 403
    assert "whitelist_enabled" in err.value.detail
    assert "whitelist_enabled" not in store


async def test_a_foreign_field_smuggled_alongside_an_allowed_one_is_rejected(
    store, as_sprachexperte
):
    """Der ganze Aufruf faellt, nicht nur das fremde Feld.

    Sonst waere das Ergebnis halb gespeichert und niemand wuesste, welche
    Haelfte.
    """
    with pytest.raises(HTTPException) as err:
        await admin_settings.update_settings(
            UpdateSettingsRequest(
                language_diagnosis_prompt="Sprich einfach.",
                whitelist_enabled=True,
            ),
            as_sprachexperte,
            "de",
        )
    assert err.value.status_code == 403
    assert store == {}


async def test_admin_may_save_everything(store):
    await admin_settings.update_settings(
        UpdateSettingsRequest(whitelist_enabled=True, ocr_enabled=False),
        {"role": "admin"},
        "de",
    )
    assert store["whitelist_enabled"] == "true"
    assert store["ocr_enabled"] == "false"


async def test_a_field_nobody_owns_is_admin_only(store, monkeypatch, as_sprachexperte):
    """Ein neues Feld ohne Eintrag im Katalog ist gesperrt, nicht offen."""
    monkeypatch.delitem(
        admin_settings.SETTING_FIELD_PERMISSIONS, "language_diagnosis_prompt"
    )
    with pytest.raises(HTTPException) as err:
        await admin_settings.update_settings(
            UpdateSettingsRequest(language_diagnosis_prompt="x"), as_sprachexperte, "de"
        )
    assert err.value.status_code == 403


# ── Keine Rechteerhöhung ─────────────────────────────────────────────────────

def test_you_cannot_grant_what_you_do_not_have():
    actor = custom_role_permissions([PERM_AIA_USE, PERM_SET_USERS_ROLES])
    with pytest.raises(HTTPException) as err:
        assert_may_grant(actor, [PERM_SET_SYSTEM], "de")
    assert err.value.status_code == 403


def test_you_may_grant_what_you_have():
    actor = custom_role_permissions([PERM_AIA_USE, PERM_SET_USERS_ROLES])
    assert_may_grant(actor, [PERM_AIA_USE, PERM_SET_USERS_ROLES], "de")


def test_the_admin_may_grant_anything():
    assert_may_grant(permissions_for_system_role("admin"), [PERM_SET_SYSTEM], "de")


# ── Die Matrix-API ───────────────────────────────────────────────────────────
# Die Endpunkte werden direkt aufgerufen. Ein Testclient zoege die Middleware
# mit, die im lokalen Betrieb an die Datenbank geht, und die pruefen wir hier
# nicht. Der Torwaechter selbst ist ein gewoehnlicher Aufruf und laesst sich
# genauso direkt pruefen.

from src.routes.admin import roles as roles_route  # noqa: E402
from src.routes.admin.roles import PermissionTogglePayload  # noqa: E402


def _as_role(monkeypatch, keys):
    """Ein Nutzer mit eigener Rolle, deren Rechte die genannten Schluessel sind."""
    from src import database

    monkeypatch.setattr(
        database, "get_custom_role",
        lambda role_id: {"id": role_id, "name": "Rolle", "permissions": list(keys)},
    )
    return {"role": "custom", "custom_role_id": 9, "email": "wer@th-luebeck.de"}


ADMIN = {"role": "admin", "email": "a@th-luebeck.de"}


async def test_matrix_lists_groups_system_roles_and_own_roles(monkeypatch):
    monkeypatch.setattr(
        roles_route.db,
        "list_custom_roles",
        lambda: [{"id": 1, "name": "Sprachexperte", "permissions": list(SPRACHEXPERTE)}],
    )
    body = await roles_route.list_roles(admin=ADMIN)

    # Jede Zeile des Katalogs steht in genau einer Gruppe, in Katalogreihenfolge.
    # Wie die Gruppen heissen und in welchem Kapitel sie stehen, prueft
    # test_permission_matrix_layout.
    rows = [k for g in body["groups"] for k in g["permissions"]]
    assert rows == list(ALL_PERMISSION_KEYS)
    assert [r["key"] for r in body["system_roles"]] == ["admin", "staff", "user"]
    assert body["custom_roles"][0]["name"] == "Sprachexperte"
    # Der Administrator darf jedes Haekchen setzen.
    assert PERM_SET_SYSTEM in body["grantable"]


async def test_a_role_manager_only_sees_its_own_rights_as_grantable(monkeypatch):
    keys = [PERM_AIA_USE, PERM_SET_USERS_ROLES, PERM_SET_AIA_LEVEL]
    actor = _as_role(monkeypatch, keys)
    monkeypatch.setattr(roles_route.db, "list_custom_roles", lambda: [])

    body = await roles_route.list_roles(admin=actor)
    assert set(body["grantable"]) == set(keys)
    assert PERM_SET_SYSTEM not in body["grantable"]


async def test_toggle_saves_a_single_checkbox(monkeypatch):
    seen = {}
    monkeypatch.setattr(
        roles_route.db, "get_custom_role",
        lambda role_id: {"id": role_id, "name": "R", "permissions": []},
    )

    def _set(role_id, key, granted):
        seen.update(role_id=role_id, key=key, granted=granted)
        return [key] if granted else []

    monkeypatch.setattr(roles_route.db, "set_custom_role_permission", _set)

    out = await roles_route.toggle_role_permission(
        3, PermissionTogglePayload(key=PERM_SET_AIA_LEVEL, granted=True), ADMIN, "de"
    )
    assert seen == {"role_id": 3, "key": PERM_SET_AIA_LEVEL, "granted": True}
    assert out["permissions"] == [PERM_SET_AIA_LEVEL]


async def test_toggle_rejects_an_unknown_key():
    with pytest.raises(HTTPException) as err:
        await roles_route.toggle_role_permission(
            3, PermissionTogglePayload(key="erfunden", granted=True), ADMIN, "de"
        )
    assert err.value.status_code == 400


async def test_toggle_refuses_to_grant_beyond_own_rights(monkeypatch):
    actor = _as_role(monkeypatch, [PERM_AIA_USE, PERM_SET_USERS_ROLES])
    monkeypatch.setattr(
        roles_route.db, "get_custom_role",
        lambda role_id: {"id": role_id, "name": "Ziel", "permissions": []},
    )
    with pytest.raises(HTTPException) as err:
        await roles_route.toggle_role_permission(
            3, PermissionTogglePayload(key=PERM_SET_SYSTEM, granted=True), actor, "de"
        )
    assert err.value.status_code == 403


async def test_taking_a_right_away_is_always_allowed(monkeypatch):
    """Wegnehmen kann niemanden erhoehen, also braucht es dafuer kein Recht."""
    actor = _as_role(monkeypatch, [PERM_AIA_USE, PERM_SET_USERS_ROLES])
    monkeypatch.setattr(
        roles_route.db, "get_custom_role",
        lambda role_id: {"id": role_id, "name": "Ziel", "permissions": [PERM_SET_SYSTEM]},
    )
    monkeypatch.setattr(roles_route.db, "set_custom_role_permission", lambda *a: [])

    out = await roles_route.toggle_role_permission(
        3, PermissionTogglePayload(key=PERM_SET_SYSTEM, granted=False), actor, "de"
    )
    assert out["permissions"] == []


async def test_without_the_roles_right_the_matrix_stays_shut(monkeypatch):
    actor = _as_role(monkeypatch, SPRACHEXPERTE)
    with pytest.raises(HTTPException) as err:
        await roles_route._require(user=actor, locale="de")
    assert err.value.status_code == 403


async def test_with_the_roles_right_the_gate_opens(monkeypatch):
    actor = _as_role(monkeypatch, [PERM_AIA_USE, PERM_SET_USERS_ROLES])
    assert await roles_route._require(user=actor, locale="de") is actor


# ── Die Seiten selbst ────────────────────────────────────────────────────────

def test_sprachexperte_reaches_the_area_but_not_the_whitelist(as_sprachexperte):
    perms = permissions_of(as_sprachexperte)
    assert perms.allow_admin_panel is True
    assert perms.has(PERM_SET_AIA_LEVEL) is True
    assert perms.has(PERM_SET_USERS_WHITELIST) is False
    assert perms.has(PERM_SET_SYSTEM) is False


# ── Doppelter Rollenname ─────────────────────────────────────────────────────

async def test_creating_a_role_twice_says_so(monkeypatch):
    from src.features.admin.repository.roles import RoleNameTaken

    def _boom(name, permissions):
        raise RoleNameTaken(name)

    monkeypatch.setattr(roles_route.db, "create_custom_role", _boom)
    with pytest.raises(HTTPException) as err:
        await roles_route.create_role(
            roles_route.RolePayload(name="Sprachexperte", permissions=[]), ADMIN, "de"
        )
    assert err.value.status_code == 409
    assert "Sprachexperte" in err.value.detail


async def test_renaming_onto_an_existing_name_says_so(monkeypatch):
    from src.features.admin.repository.roles import RoleNameTaken

    monkeypatch.setattr(
        roles_route.db, "get_custom_role",
        lambda role_id: {"id": role_id, "name": "Alt", "permissions": []},
    )

    def _boom(role_id, name):
        raise RoleNameTaken(name)

    monkeypatch.setattr(roles_route.db, "rename_custom_role", _boom)
    with pytest.raises(HTTPException) as err:
        await roles_route.rename_role(
            3, roles_route.RoleNamePayload(name="Sprachexperte"), ADMIN, "de"
        )
    assert err.value.status_code == 409
    assert "Sprachexperte" in err.value.detail
