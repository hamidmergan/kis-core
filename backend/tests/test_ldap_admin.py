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
