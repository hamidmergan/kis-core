"""One account, created the same way for both ways in."""

from unittest.mock import patch

import pytest

from src.features.accounts.provisioning import provision_account


def _anlegen(**abweichungen):
    argumente = dict(
        settings=object(),
        uid="max.mustermann",
        given_name="Max",
        surname="Mustermann",
        email="max.mustermann@demo.kis.local",
        role="staff",
        custom_role_id=None,
        password="geheim123",
    )
    argumente.update(abweichungen)
    return provision_account(**argumente)


def test_creates_ldap_user_whitelist_entry_and_row():
    with patch("src.features.accounts.provisioning.create_ldap_user") as ldap, \
         patch("src.features.accounts.provisioning.database.add_to_whitelist") as weiss, \
         patch("src.features.accounts.provisioning.database.create_user", return_value=42):
        daten = _anlegen()

    assert ldap.call_args.kwargs["uid"] == "max.mustermann"
    assert ldap.call_args.kwargs["employee_type"] == "staff"
    weiss.assert_called_once_with("max.mustermann@demo.kis.local")
    assert daten["user_id"] == 42
    assert daten["username"] == "max.mustermann"
    assert daten["display_name"] == "Max Mustermann"


def test_falls_back_to_the_user_name_when_no_name_was_given():
    with patch("src.features.accounts.provisioning.create_ldap_user"), \
         patch("src.features.accounts.provisioning.database.add_to_whitelist"), \
         patch("src.features.accounts.provisioning.database.create_user", return_value=42):
        daten = _anlegen(given_name="", surname="")

    assert daten["display_name"] == "max.mustermann"


def test_a_custom_role_is_set_afterwards():
    with patch("src.features.accounts.provisioning.create_ldap_user"), \
         patch("src.features.accounts.provisioning.database.add_to_whitelist"), \
         patch("src.features.accounts.provisioning.database.create_user", return_value=42), \
         patch("src.features.accounts.provisioning.database.set_user_role") as rolle:
        daten = _anlegen(role="custom", custom_role_id=3)

    rolle.assert_called_once_with(42, "custom", 3)
    assert daten["custom_role_id"] == 3


def test_only_staff_becomes_staff_in_ldap():
    with patch("src.features.accounts.provisioning.create_ldap_user") as ldap, \
         patch("src.features.accounts.provisioning.database.add_to_whitelist"), \
         patch("src.features.accounts.provisioning.database.create_user", return_value=42), \
         patch("src.features.accounts.provisioning.database.set_user_role"):
        _anlegen(role="custom", custom_role_id=3)

    assert ldap.call_args.kwargs["employee_type"] == "user"


def test_a_failing_ldap_call_stops_everything():
    with patch("src.features.accounts.provisioning.create_ldap_user", side_effect=RuntimeError("ldap")), \
         patch("src.features.accounts.provisioning.database.add_to_whitelist") as weiss, \
         patch("src.features.accounts.provisioning.database.create_user") as anlegen:
        with pytest.raises(RuntimeError):
            _anlegen()

    weiss.assert_not_called()
    anlegen.assert_not_called()
