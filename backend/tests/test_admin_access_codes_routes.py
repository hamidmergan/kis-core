"""Access codes in the admin area: create, list, switch off, delete."""

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
    assert r.json()["code"].startswith("KIS-")
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
