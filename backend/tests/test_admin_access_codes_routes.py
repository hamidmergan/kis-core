"""Access codes in the admin area: create, list, switch off, delete."""

import re
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.permissions_registry import PERM_SET_USERS_ALL

MORGEN = datetime.now() + timedelta(days=30)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("LDAP_USER_CREATION_ENABLED", "true")
    monkeypatch.setenv("LDAP_BASE_DN", "dc=th-luebeck,dc=de")
    monkeypatch.setenv("LDAP_SERVER", "ldap://openldap")

    from src.dependencies import get_current_user, get_settings
    from src.security.auth import verify_auth
    from src.app import app

    get_settings.cache_clear()
    app.dependency_overrides[verify_auth] = lambda: None
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": 1, "email": "admin@th-luebeck.de", "role": "admin",
    }
    yield TestClient(app)
    app.dependency_overrides.clear()
    get_settings.cache_clear()


@pytest.fixture
def limited_client(monkeypatch):
    """An admin whose custom role holds only user administration, nothing else."""
    monkeypatch.setenv("LDAP_USER_CREATION_ENABLED", "true")
    monkeypatch.setenv("LDAP_BASE_DN", "dc=th-luebeck,dc=de")
    monkeypatch.setenv("LDAP_SERVER", "ldap://openldap")

    from src import database
    from src.dependencies import get_current_user, get_settings
    from src.security.auth import verify_auth
    from src.app import app

    get_settings.cache_clear()
    monkeypatch.setattr(
        database, "get_custom_role",
        lambda role_id: {"id": role_id, "name": "Nutzerverwaltung", "permissions": [PERM_SET_USERS_ALL]},
    )
    app.dependency_overrides[verify_auth] = lambda: None
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": 2, "email": "eingeschraenkt@th-luebeck.de",
        "role": "custom", "custom_role_id": 5,
    }
    yield TestClient(app)
    app.dependency_overrides.clear()
    get_settings.cache_clear()


@pytest.fixture
def client_ohne_recht(monkeypatch):
    """A caller with no admin rights at all, to prove the gate itself holds."""
    monkeypatch.setenv("LDAP_USER_CREATION_ENABLED", "true")
    monkeypatch.setenv("LDAP_BASE_DN", "dc=th-luebeck,dc=de")
    monkeypatch.setenv("LDAP_SERVER", "ldap://openldap")

    from src.dependencies import get_current_user, get_settings
    from src.security.auth import verify_auth
    from src.app import app

    get_settings.cache_clear()
    app.dependency_overrides[verify_auth] = lambda: None
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": 3, "email": "student@th-luebeck.de", "role": "user",
    }
    yield TestClient(app)
    app.dependency_overrides.clear()
    get_settings.cache_clear()


def test_creating_a_code_returns_the_readable_code(client):
    with patch("src.routes.admin.access_codes.repo.create_code", return_value=7) as anlegen:
        r = client.post("/admin/access-codes", json={
            "label": "Kollegen August", "max_uses": 50,
            "valid_days": 30, "access_days": 14, "kis_role": "staff",
        })

    assert r.status_code == 200
    assert re.fullmatch(r"KIS-[A-Z2-9]{4}-[A-Z2-9]{4}", r.json()["code"])
    assert anlegen.call_args.kwargs["max_uses"] == 50
    assert anlegen.call_args.kwargs["access_days"] == 14
    assert anlegen.call_args.kwargs["created_by"] == 1


def test_creating_a_code_with_unlimited_access(client):
    with patch("src.routes.admin.access_codes.repo.create_code", return_value=7) as anlegen:
        r = client.post("/admin/access-codes", json={
            "label": "Kollegen August", "max_uses": 50,
            "valid_days": 30, "access_days": None, "kis_role": "staff",
        })

    assert r.status_code == 200
    assert anlegen.call_args.kwargs["access_days"] is None


def test_creating_a_code_with_access_days_above_the_cap_is_refused(client):
    with patch("src.routes.admin.access_codes.repo.create_code") as anlegen:
        r = client.post("/admin/access-codes", json={
            "label": "Kollegen August", "max_uses": 50,
            "valid_days": 30, "access_days": 31, "kis_role": "staff",
        })

    assert r.status_code in (400, 422)
    anlegen.assert_not_called()


def test_creating_a_code_without_a_name_is_refused(client):
    with patch("src.routes.admin.access_codes.repo.create_code") as anlegen:
        r = client.post("/admin/access-codes", json={
            "label": "   ", "max_uses": 50, "valid_days": 30,
            "access_days": 14, "kis_role": "staff",
        })

    assert r.status_code in (400, 422)
    anlegen.assert_not_called()


def test_a_custom_role_has_to_exist(client):
    with patch("src.routes.admin.access_codes.database.get_custom_role", return_value=None), \
         patch("src.routes.admin.access_codes.repo.create_code") as anlegen:
        r = client.post("/admin/access-codes", json={
            "label": "Sprachenzentrum", "max_uses": 10, "valid_days": 30,
            "access_days": 21, "kis_role": "custom", "custom_role_id": 99,
        })

    assert r.status_code == 400
    anlegen.assert_not_called()


def test_the_list_carries_the_state_of_every_code(client):
    eintraege = [
        {"id": 1, "code": "KIS-AAAA-BBBB", "label": "A", "role": "staff",
         "custom_role_id": None, "max_uses": 50, "used_count": 3,
         "valid_until": MORGEN, "access_days": 14, "active": True,
         "created_at": MORGEN, "created_by": 1},
        {"id": 2, "code": "KIS-CCCC-DDDD", "label": "B", "role": "user",
         "custom_role_id": None, "max_uses": 5, "used_count": 5,
         "valid_until": MORGEN, "access_days": 14, "active": True,
         "created_at": MORGEN, "created_by": 1},
        {"id": 3, "code": "KIS-EEEE-FFFF", "label": "C", "role": "user",
         "custom_role_id": None, "max_uses": 5, "used_count": 0,
         "valid_until": MORGEN, "access_days": 14, "active": False,
         "created_at": MORGEN, "created_by": 1},
    ]
    with patch("src.routes.admin.access_codes.repo.list_codes", return_value=eintraege):
        r = client.get("/admin/access-codes")

    zustaende = [e["status"] for e in r.json()["codes"]]
    assert zustaende == ["active", "full", "disabled"]


def test_switching_a_code_off(client):
    with patch("src.routes.admin.access_codes.repo.set_active", return_value=True) as um:
        r = client.patch("/admin/access-codes/7", json={"active": False})

    assert r.status_code == 200
    um.assert_called_once_with(7, False)


def test_switching_an_unknown_code_reports_not_found(client):
    with patch("src.routes.admin.access_codes.repo.set_active", return_value=False):
        r = client.patch("/admin/access-codes/999", json={"active": False})
    assert r.status_code == 404


def test_deleting_a_code(client):
    with patch("src.routes.admin.access_codes.repo.delete_code", return_value=True) as weg:
        r = client.delete("/admin/access-codes/7")

    assert r.status_code == 200
    weg.assert_called_once_with(7)


def test_deleting_an_unknown_code_reports_not_found(client):
    with patch("src.routes.admin.access_codes.repo.delete_code", return_value=False):
        r = client.delete("/admin/access-codes/999")
    assert r.status_code == 404


def test_a_role_beyond_the_admins_own_permissions_is_refused(limited_client):
    with patch("src.routes.admin.access_codes.repo.create_code") as anlegen:
        r = limited_client.post("/admin/access-codes", json={
            "label": "Zuviel", "max_uses": 5, "valid_days": 30,
            "access_days": 14, "kis_role": "staff",
        })

    assert r.status_code == 403
    anlegen.assert_not_called()


def test_without_the_permission_the_list_stays_shut(client_ohne_recht):
    r = client_ohne_recht.get("/admin/access-codes")
    assert r.status_code == 403


GESTERN = datetime.now() - timedelta(days=1)


def test_the_user_list_carries_the_state_of_every_account(client):
    konten = [
        {"id": 1, "ldap_username": "abc12345", "created_at": MORGEN,
         "access_expires_at": MORGEN, "active": True},
        {"id": 2, "ldap_username": "def67890", "created_at": MORGEN,
         "access_expires_at": GESTERN, "active": True},
        {"id": 3, "ldap_username": "ghi13579", "created_at": MORGEN,
         "access_expires_at": MORGEN, "active": False},
        {"id": 4, "ldap_username": "jkl24680", "created_at": MORGEN,
         "access_expires_at": None, "active": True},
    ]
    with patch("src.routes.admin.access_codes.repo.list_users_for_code", return_value=konten):
        r = client.get("/admin/access-codes/7/users")

    assert r.status_code == 200
    zustaende = [u["status"] for u in r.json()["users"]]
    assert zustaende == ["active", "expired", "disabled", "active"], \
        "eine leere Frist heisst unbegrenzt gueltig, nicht abgelaufen"


def test_resetting_a_password_calls_ldap_with_the_right_uid(client):
    konto = {"id": 42, "ldap_username": "abc12345", "access_code_id": 7}
    with patch("src.routes.admin.access_codes.database.get_user_by_id", return_value=konto), \
         patch("src.routes.admin.access_codes.set_ldap_password") as ldap_call:
        r = client.post("/admin/access-codes/users/42/password")

    assert r.status_code == 200
    body = r.json()
    assert body["username"] == "abc12345"
    assert body["password"]
    assert ldap_call.call_args.kwargs["uid"] == "abc12345"


def test_resetting_a_password_for_an_account_without_a_code_is_refused(client):
    konto = {"id": 5, "ldap_username": "staffuser", "access_code_id": None}
    with patch("src.routes.admin.access_codes.database.get_user_by_id", return_value=konto), \
         patch("src.routes.admin.access_codes.set_ldap_password") as ldap_call:
        r = client.post("/admin/access-codes/users/5/password")

    assert r.status_code == 403
    ldap_call.assert_not_called()


def test_the_activity_route_returns_modules_and_messages(client):
    konto = {"id": 42, "ldap_username": "abc12345", "access_code_id": 7}
    module = [{"workspace_id": 1, "title": "Deutsch A1", "relation": "owner", "since": MORGEN}]
    nachrichten = [{
        "role": "user", "content": "Was bedeutet das?", "created_at": MORGEN,
        "failed": False, "aborted": False, "workspace_title": "Deutsch A1",
    }]
    with patch("src.routes.admin.access_codes.database.get_user_by_id", return_value=konto), \
         patch("src.routes.admin.access_codes.repo.list_workspaces_for_user", return_value=module) as ws, \
         patch("src.routes.admin.access_codes.repo.list_messages_for_user", return_value=nachrichten) as msg:
        r = client.get("/admin/access-codes/users/42/activity")

    assert r.status_code == 200
    body = r.json()
    assert body["workspaces"][0]["relation"] == "owner"
    assert body["messages"][0]["role"] == "user"
    ws.assert_called_once_with(42)
    msg.assert_called_once_with(42)


def test_the_activity_route_refuses_an_account_without_a_code(client):
    konto = {"id": 5, "ldap_username": "staffuser", "access_code_id": None}
    with patch("src.routes.admin.access_codes.database.get_user_by_id", return_value=konto), \
         patch("src.routes.admin.access_codes.repo.list_workspaces_for_user") as ws, \
         patch("src.routes.admin.access_codes.repo.list_messages_for_user") as msg:
        r = client.get("/admin/access-codes/users/5/activity")

    assert r.status_code == 403
    ws.assert_not_called()
    msg.assert_not_called()


def test_the_activity_route_refuses_an_unknown_account(client):
    with patch("src.routes.admin.access_codes.database.get_user_by_id", return_value=None), \
         patch("src.routes.admin.access_codes.repo.list_workspaces_for_user") as ws, \
         patch("src.routes.admin.access_codes.repo.list_messages_for_user") as msg:
        r = client.get("/admin/access-codes/users/999/activity")

    assert r.status_code == 403
    ws.assert_not_called()
    msg.assert_not_called()


class _FakeActivityCursor:
    """Captures every execute() call so the SQL LIMIT can be checked."""

    def __init__(self):
        self.calls: list[tuple] = []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self.calls.append((" ".join(sql.split()), params))

    def fetchall(self):
        return []


class _FakeActivityConn:
    def __init__(self, cursor):
        self._cursor = cursor

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self, **kwargs):
        return self._cursor


def test_the_message_cap_is_fifty(monkeypatch):
    from src.features.access_codes import repository as repo

    cursor = _FakeActivityCursor()
    monkeypatch.setattr(repo, "get_connection", lambda: _FakeActivityConn(cursor))

    repo.list_messages_for_user(42)

    sql, params = cursor.calls[0]
    assert "LIMIT %s" in sql
    assert params[-1] == 50, "die Obergrenze muss bei 50 liegen, sonst waechst die Abfrage unbegrenzt"
