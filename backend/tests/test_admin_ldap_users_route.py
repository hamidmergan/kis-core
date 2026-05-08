from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("LDAP_USER_CREATION_ENABLED", "true")
    monkeypatch.setenv("LDAP_BASE_DN", "dc=th-luebeck,dc=de")
    monkeypatch.setenv("LDAP_BIND_DN", "cn=admin,dc=th-luebeck,dc=de")
    monkeypatch.setenv("LDAP_BIND_PASSWORD", "admin")
    monkeypatch.setenv("LDAP_SERVER", "ldap://openldap")

    from src.dependencies import get_admin_user, get_settings
    from src.security.auth import verify_auth
    from src.app import app

    get_settings.cache_clear()
    app.dependency_overrides[verify_auth] = lambda: None
    app.dependency_overrides[get_admin_user] = lambda: {"user_id": 1, "email": "admin@th-luebeck.de"}
    yield TestClient(app)
    app.dependency_overrides.clear()
    get_settings.cache_clear()


def test_create_ldap_user_returns_password(client):
    with patch("src.routes.admin.ldap_users.create_ldap_user", return_value="GENERATED-pw"):
        r = client.post(
            "/admin/ldap-users",
            json={
                "uid": "newone",
                "given_name": "New",
                "surname": "One",
                "email": "n@th-luebeck.de",
                "employee_type": "staff",
            },
        )
    assert r.status_code == 200
    body = r.json()
    assert body["uid"] == "newone"
    assert body["generated_password"] == "GENERATED-pw"


def test_create_ldap_user_conflict_returns_409(client):
    from src.ldap_admin import LdapUserExistsError

    with patch(
        "src.routes.admin.ldap_users.create_ldap_user",
        side_effect=LdapUserExistsError("newone"),
    ):
        r = client.post(
            "/admin/ldap-users",
            json={
                "uid": "newone",
                "given_name": "N",
                "surname": "O",
                "email": "n@th-luebeck.de",
                "employee_type": "staff",
            },
        )
    assert r.status_code == 409


def test_create_ldap_user_validation_returns_400(client):
    from src.ldap_admin import LdapValidationError

    with patch(
        "src.routes.admin.ldap_users.create_ldap_user",
        side_effect=LdapValidationError("uid", "must match pattern"),
    ):
        r = client.post(
            "/admin/ldap-users",
            json={
                "uid": "BAD",
                "given_name": "N",
                "surname": "O",
                "email": "n@th-luebeck.de",
                "employee_type": "staff",
            },
        )
    assert r.status_code == 400


def test_create_ldap_user_404_when_flag_off(monkeypatch):
    monkeypatch.delenv("LDAP_USER_CREATION_ENABLED", raising=False)
    from src.dependencies import get_admin_user, get_settings
    from src.security.auth import verify_auth
    from src.app import app

    get_settings.cache_clear()
    app.dependency_overrides[verify_auth] = lambda: None
    app.dependency_overrides[get_admin_user] = lambda: {"user_id": 1, "email": "admin@th-luebeck.de"}
    try:
        c = TestClient(app)
        r = c.post(
            "/admin/ldap-users",
            json={
                "uid": "x1",
                "given_name": "A",
                "surname": "B",
                "email": "a@b.de",
                "employee_type": "staff",
            },
        )
        assert r.status_code == 404
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()
