"""The admin account from the .env, created once and never overwritten."""

from unittest.mock import patch

from src.features.accounts.env_admin import ensure_env_admin


def test_nothing_happens_without_a_mail_address():
    with patch("src.features.accounts.env_admin.database.create_user") as anlegen:
        assert ensure_env_admin("", "geheim123") is None
    anlegen.assert_not_called()


def test_nothing_happens_without_a_password():
    with patch("src.features.accounts.env_admin.database.create_user") as anlegen:
        assert ensure_env_admin("admin@th-luebeck.de", "") is None
    anlegen.assert_not_called()


def test_the_account_is_created_with_the_local_part_as_user_name():
    with patch("src.features.accounts.env_admin.database.get_user_by_email", return_value=None), \
         patch("src.features.accounts.env_admin.database.get_user_by_username", return_value=None), \
         patch("src.features.accounts.env_admin.database.add_to_whitelist"), \
         patch("src.features.accounts.env_admin.database.create_user", return_value=7) as anlegen:
        assert ensure_env_admin("admin@th-luebeck.de", "geheim123") == 7

    kwargs = anlegen.call_args.kwargs
    assert kwargs["ldap_username"] == "admin"
    assert kwargs["email"] == "admin@th-luebeck.de"
    assert kwargs["role"] == "admin"
    assert kwargs["active"] == 1
    assert kwargs["password_hash"].startswith("$2")


def test_an_existing_account_keeps_its_password():
    vorhanden = {"id": 7, "password_hash": "$2b$12$selbstgesetzt"}
    with patch("src.features.accounts.env_admin.database.get_user_by_email", return_value=vorhanden), \
         patch("src.features.accounts.env_admin.database.create_user") as anlegen, \
         patch("src.features.accounts.env_admin.database.set_user_password") as setzen:
        assert ensure_env_admin("admin@th-luebeck.de", "geheim123") == 7

    anlegen.assert_not_called()
    setzen.assert_not_called()


def test_an_existing_account_without_a_password_gets_the_one_from_the_env():
    # Migrated accounts land here, the .env is their way back in.
    vorhanden = {"id": 7, "password_hash": None}
    with patch("src.features.accounts.env_admin.database.get_user_by_email", return_value=vorhanden), \
         patch("src.features.accounts.env_admin.database.create_user") as anlegen, \
         patch("src.features.accounts.env_admin.database.set_user_password") as setzen:
        assert ensure_env_admin("admin@th-luebeck.de", "geheim123") == 7

    anlegen.assert_not_called()
    assert setzen.call_args.args[0] == 7
    assert setzen.call_args.args[1].startswith("$2")


def test_a_taken_user_name_gets_a_number_appended():
    def belegt(name):
        return {"id": 1} if name == "admin" else None

    with patch("src.features.accounts.env_admin.database.get_user_by_email", return_value=None), \
         patch("src.features.accounts.env_admin.database.get_user_by_username", side_effect=belegt), \
         patch("src.features.accounts.env_admin.database.add_to_whitelist"), \
         patch("src.features.accounts.env_admin.database.create_user", return_value=8) as anlegen:
        ensure_env_admin("admin@th-luebeck.de", "geheim123")

    assert anlegen.call_args.kwargs["ldap_username"] == "admin2"


def test_a_mail_address_without_a_usable_local_part_falls_back():
    with patch("src.features.accounts.env_admin.database.get_user_by_email", return_value=None), \
         patch("src.features.accounts.env_admin.database.get_user_by_username", return_value=None), \
         patch("src.features.accounts.env_admin.database.add_to_whitelist"), \
         patch("src.features.accounts.env_admin.database.create_user", return_value=9) as anlegen:
        ensure_env_admin("!@th-luebeck.de", "geheim123")

    assert anlegen.call_args.kwargs["ldap_username"] == "admin"
