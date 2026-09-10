from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ACCOUNT_CREATION_ENABLED", "true")
    monkeypatch.setenv("LDAP_BASE_DN", "dc=th-luebeck,dc=de")
    monkeypatch.setenv("LDAP_BIND_DN", "cn=admin,dc=th-luebeck,dc=de")
    monkeypatch.setenv("LDAP_BIND_PASSWORD", "admin")
    monkeypatch.setenv("LDAP_SERVER", "ldap://openldap")

    from src.dependencies import get_current_user, get_settings
    from src.security.auth import verify_auth
    from src.app import app

    get_settings.cache_clear()
    app.dependency_overrides[verify_auth] = lambda: None
    # The route hangs off the permission, no longer off the role.
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": 1, "email": "admin@th-luebeck.de", "role": "admin",
    }
    yield TestClient(app)
    app.dependency_overrides.clear()
    get_settings.cache_clear()


def _patch_db_writes():
    """Stack of patches for the post-LDAP DB write path."""
    return (
        patch("src.routes.admin.ldap_users.database.add_to_whitelist"),
        patch("src.routes.admin.ldap_users.database.create_user", return_value=42),
        patch("src.routes.admin.ldap_users.database.set_user_role"),
        patch("src.routes.admin.ldap_users.database.get_custom_role", return_value={"id": 7, "name": "Tester"}),
    )


def test_create_ldap_user_with_staff_role(client):
    whitelist_p, create_p, set_role_p, _ = _patch_db_writes()
    with whitelist_p as add_wl, create_p as create_user, set_role_p as set_role, \
         patch("src.routes.admin.ldap_users.create_ldap_user", return_value="GEN-pw") as ldap_add:
        r = client.post(
            "/admin/ldap-users",
            json={
                "uid": "newone",
                "given_name": "New",
                "surname": "One",
                "email": "n@th-luebeck.de",
                "kis_role": "staff",
            },
        )
    assert r.status_code == 200
    body = r.json()
    assert body == {"uid": "newone", "generated_password": "GEN-pw"}
    # employeeType=staff goes to LDAP
    assert ldap_add.call_args.kwargs["employee_type"] == "staff"
    # DB row created with role=staff
    assert create_user.call_args.kwargs["role"] == "staff"
    assert create_user.call_args.kwargs["active"] == 1
    add_wl.assert_called_once_with("n@th-luebeck.de")
    set_role.assert_not_called()


def test_create_ldap_user_with_user_role(client):
    whitelist_p, create_p, set_role_p, _ = _patch_db_writes()
    with whitelist_p, create_p as create_user, set_role_p as set_role, \
         patch("src.routes.admin.ldap_users.create_ldap_user", return_value="GEN-pw") as ldap_add:
        r = client.post(
            "/admin/ldap-users",
            json={
                "uid": "studi",
                "given_name": "St",
                "surname": "U",
                "email": "s@th-luebeck.de",
                "kis_role": "user",
            },
        )
    assert r.status_code == 200
    assert ldap_add.call_args.kwargs["employee_type"] == "user"
    assert create_user.call_args.kwargs["role"] == "user"
    set_role.assert_not_called()


def test_create_ldap_user_with_custom_role(client):
    whitelist_p, create_p, set_role_p, get_cr_p = _patch_db_writes()
    with whitelist_p, create_p as create_user, set_role_p as set_role, get_cr_p as get_cr, \
         patch("src.routes.admin.ldap_users.create_ldap_user", return_value="GEN-pw") as ldap_add:
        r = client.post(
            "/admin/ldap-users",
            json={
                "uid": "tester1",
                "given_name": "T",
                "surname": "Est",
                "email": "t@th-luebeck.de",
                "kis_role": "custom",
                "custom_role_id": 7,
            },
        )
    assert r.status_code == 200
    # LDAP gets neutral employeeType=user (custom roles aren't an LDAP concept)
    assert ldap_add.call_args.kwargs["employee_type"] == "user"
    # Custom role validated up front
    get_cr.assert_called_once_with(7)
    # DB row created with role=custom, then set_user_role binds custom_role_id
    assert create_user.call_args.kwargs["role"] == "custom"
    set_role.assert_called_once_with(42, "custom", 7)


def test_create_ldap_user_custom_without_id_returns_422(client):
    r = client.post(
        "/admin/ldap-users",
        json={
            "uid": "tester2",
            "given_name": "T",
            "surname": "Est",
            "email": "t@th-luebeck.de",
            "kis_role": "custom",
        },
    )
    assert r.status_code == 422


def test_create_ldap_user_custom_unknown_id_returns_400(client):
    with patch(
        "src.routes.admin.ldap_users.database.get_custom_role",
        return_value=None,
    ):
        r = client.post(
            "/admin/ldap-users",
            json={
                "uid": "tester3",
                "given_name": "T",
                "surname": "Est",
                "email": "t@th-luebeck.de",
                "kis_role": "custom",
                "custom_role_id": 999,
            },
        )
    assert r.status_code == 400


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
                "kis_role": "staff",
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
                "kis_role": "staff",
            },
        )
    assert r.status_code == 400


def test_create_ldap_user_service_error_returns_500(client):
    from src.ldap_admin import LdapServiceError

    with patch(
        "src.routes.admin.ldap_users.create_ldap_user",
        side_effect=LdapServiceError("LDAP service bind failed: connection refused"),
    ):
        r = client.post(
            "/admin/ldap-users",
            json={
                "uid": "newone",
                "given_name": "N",
                "surname": "O",
                "email": "n@th-luebeck.de",
                "kis_role": "staff",
            },
        )
    assert r.status_code == 500
    assert r.json()["detail"]


def test_create_ldap_user_db_write_failure_returns_500(client):
    """LDAP add succeeds but DB write fails -> 500 with dbWriteFailed key."""
    with patch("src.routes.admin.ldap_users.create_ldap_user", return_value="GEN-pw"), \
         patch("src.routes.admin.ldap_users.database.add_to_whitelist"), \
         patch(
             "src.routes.admin.ldap_users.database.create_user",
             side_effect=RuntimeError("DB down"),
         ):
        r = client.post(
            "/admin/ldap-users",
            json={
                "uid": "newone",
                "given_name": "N",
                "surname": "O",
                "email": "n@th-luebeck.de",
                "kis_role": "staff",
            },
        )
    assert r.status_code == 500


def test_create_ldap_user_404_when_flag_off(monkeypatch):
    monkeypatch.delenv("ACCOUNT_CREATION_ENABLED", raising=False)
    from src.dependencies import get_current_user, get_settings
    from src.security.auth import verify_auth
    from src.app import app

    get_settings.cache_clear()
    app.dependency_overrides[verify_auth] = lambda: None
    # The route hangs off the permission, no longer off the role.
    app.dependency_overrides[get_current_user] = lambda: {
        "user_id": 1, "email": "admin@th-luebeck.de", "role": "admin",
    }
    try:
        c = TestClient(app)
        r = c.post(
            "/admin/ldap-users",
            json={
                "uid": "x1",
                "given_name": "A",
                "surname": "B",
                "email": "a@b.de",
                "kis_role": "staff",
            },
        )
        assert r.status_code == 404
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()
