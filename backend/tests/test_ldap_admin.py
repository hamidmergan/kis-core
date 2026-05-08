import base64
import hashlib

from src.ldap_admin import _make_ssha_hash


def test_ssha_hash_has_prefix_and_verifies():
    password = "correct horse battery staple"
    digest = _make_ssha_hash(password)
    assert digest.startswith("{SSHA}")

    decoded = base64.b64decode(digest[len("{SSHA}"):])
    sha_bytes, salt = decoded[:20], decoded[20:]
    assert len(salt) == 4
    expected = hashlib.sha1(password.encode("utf-8") + salt).digest()
    assert sha_bytes == expected


def test_ssha_hash_is_salted_unique():
    a = _make_ssha_hash("same-password")
    b = _make_ssha_hash("same-password")
    assert a != b  # random salt


import pytest

from src.ldap_admin import _generate_password, validate_inputs, LdapValidationError


def test_generate_password_returns_url_safe_string():
    pw = _generate_password()
    assert isinstance(pw, str)
    assert len(pw) >= 16
    # token_urlsafe alphabet
    assert all(c.isalnum() or c in "-_" for c in pw)
    # Multiple calls return distinct values
    assert _generate_password() != pw


@pytest.mark.parametrize("uid", ["a1", "ab", "valid_user.1", "u-2"])
def test_validate_inputs_accepts_valid_uid(uid):
    validate_inputs(uid=uid, given_name="A", surname="B", email="a@b.de", employee_type="staff")


@pytest.mark.parametrize("uid", ["", "A", "with space", "ümlaut", "x" * 33, "../etc"])
def test_validate_inputs_rejects_bad_uid(uid):
    with pytest.raises(LdapValidationError):
        validate_inputs(uid=uid, given_name="A", surname="B", email="a@b.de", employee_type="staff")


def test_validate_inputs_rejects_bad_email():
    with pytest.raises(LdapValidationError):
        validate_inputs(uid="ok", given_name="A", surname="B", email="not-an-email", employee_type="staff")


def test_validate_inputs_rejects_bad_employee_type():
    with pytest.raises(LdapValidationError):
        validate_inputs(uid="ok", given_name="A", surname="B", email="a@b.de", employee_type="admin")


def test_validate_inputs_rejects_blank_names():
    with pytest.raises(LdapValidationError):
        validate_inputs(uid="ok", given_name="", surname="B", email="a@b.de", employee_type="staff")
    with pytest.raises(LdapValidationError):
        validate_inputs(uid="ok", given_name="A", surname="", email="a@b.de", employee_type="staff")


from unittest.mock import MagicMock, patch

from src.ldap_admin import (
    LdapUserExistsError,
    LdapServiceError,
    create_ldap_user,
)


def _fake_settings(**overrides):
    base = MagicMock()
    base.ldap_server = "ldap://openldap"
    base.ldap_port = 389
    base.ldap_use_ssl = False
    base.ldap_base_dn = "dc=th-luebeck,dc=de"
    base.ldap_bind_dn = "cn=admin,dc=th-luebeck,dc=de"
    base.ldap_bind_password = "admin"
    base.ldap_attr_username = "uid"
    for k, v in overrides.items():
        setattr(base, k, v)
    return base


@patch("src.ldap_admin.Connection")
@patch("src.ldap_admin.Server")
def test_create_ldap_user_happy_path(server_mock, conn_cls_mock):
    conn = MagicMock()
    conn.add.return_value = True
    conn.result = {"description": "success"}
    conn_cls_mock.return_value = conn

    pw = create_ldap_user(
        settings=_fake_settings(),
        uid="newuser",
        given_name="New",
        surname="User",
        email="new@th-luebeck.de",
        employee_type="staff",
    )

    assert isinstance(pw, str) and len(pw) >= 16
    conn.add.assert_called_once()
    dn, classes, attrs = conn.add.call_args.args
    assert dn == "uid=newuser,ou=people,dc=th-luebeck,dc=de"
    assert "inetOrgPerson" in classes
    assert attrs["uid"] == "newuser"
    assert attrs["cn"] == "New User"
    assert attrs["sn"] == "User"
    assert attrs["mail"] == "new@th-luebeck.de"
    assert attrs["employeeType"] == "staff"
    assert attrs["userPassword"].startswith("{SSHA}")


@patch("src.ldap_admin.Connection")
@patch("src.ldap_admin.Server")
def test_create_ldap_user_conflict_raises(server_mock, conn_cls_mock):
    conn = MagicMock()
    conn.add.return_value = False
    conn.result = {"description": "entryAlreadyExists", "result": 68}
    conn_cls_mock.return_value = conn

    with pytest.raises(LdapUserExistsError):
        create_ldap_user(
            settings=_fake_settings(),
            uid="existing",
            given_name="A",
            surname="B",
            email="a@b.de",
            employee_type="student",
        )


@patch("src.ldap_admin.Connection")
@patch("src.ldap_admin.Server")
def test_create_ldap_user_other_failure_raises_service_error(server_mock, conn_cls_mock):
    conn = MagicMock()
    conn.add.return_value = False
    conn.result = {"description": "insufficientAccessRights", "result": 50}
    conn_cls_mock.return_value = conn

    with pytest.raises(LdapServiceError):
        create_ldap_user(
            settings=_fake_settings(),
            uid="ok",
            given_name="A",
            surname="B",
            email="a@b.de",
            employee_type="staff",
        )
