"""Moving the directory entries into the database, once and repeatable."""

import sys
from pathlib import Path
from unittest.mock import patch

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from ldap_nach_db import eintraege_aus_ldif, uebernehmen  # noqa: E402

LDIF = """dn: uid=a,ou=people,dc=th-luebeck,dc=de
objectClass: inetOrgPerson
uid: a
cn: Hans Müller
sn: Müller
mail: admin@th-luebeck.de
userPassword: {SSHA}abc123
employeeType: staff

dn: uid=b,ou=people,dc=th-luebeck,dc=de
objectClass: inetOrgPerson
uid: b
cn: Jana Schmidt
sn: Schmidt
mail: j.schmidt@th-luebeck.de
userPassword: {SSHA}def456
employeeType: student
"""


def test_both_people_are_read_out_of_the_file():
    eintraege = eintraege_aus_ldif(LDIF)
    assert [e["uid"] for e in eintraege] == ["a", "b"]
    assert eintraege[0]["cn"] == "Hans Müller"
    assert eintraege[0]["password"] == "{SSHA}abc123"
    assert eintraege[0]["employee_type"] == "staff"


def test_an_entry_without_a_uid_is_ignored():
    assert eintraege_aus_ldif("dn: ou=people,dc=th-luebeck,dc=de\nou: people\n") == []


def test_base64_values_are_decoded():
    # slapcat writes non-ASCII with a double colon and base64.
    text = "dn: uid=c,dc=x\nuid: c\ncn:: SGFucyBNw7xsbGVy\nuserPassword: {SSHA}x\n"
    assert eintraege_aus_ldif(text)[0]["cn"] == "Hans Müller"


def test_a_missing_person_is_created_with_the_hash():
    eintrag = {"uid": "a", "cn": "Hans Müller", "mail": "admin@th-luebeck.de",
               "password": "{SSHA}abc123", "employee_type": "staff"}
    with patch("ldap_nach_db.database.get_user_by_username", return_value=None), \
         patch("ldap_nach_db.database.add_to_whitelist"), \
         patch("ldap_nach_db.database.create_user", return_value=1) as anlegen:
        zahlen = uebernehmen([eintrag], auch_neue=True)

    assert zahlen["angelegt"] == 1
    kwargs = anlegen.call_args.kwargs
    assert kwargs["ldap_username"] == "a"
    assert kwargs["password_hash"] == "{SSHA}abc123"
    assert kwargs["role"] == "staff"


def test_a_student_becomes_a_plain_user():
    eintrag = {"uid": "b", "cn": "Jana", "mail": "j@x.de", "password": "{SSHA}d",
               "employee_type": "student"}
    with patch("ldap_nach_db.database.get_user_by_username", return_value=None), \
         patch("ldap_nach_db.database.add_to_whitelist"), \
         patch("ldap_nach_db.database.create_user", return_value=2) as anlegen:
        uebernehmen([eintrag], auch_neue=True)
    assert anlegen.call_args.kwargs["role"] == "user"


def test_an_existing_person_without_a_hash_only_gets_the_hash():
    eintrag = {"uid": "a", "cn": "Hans", "mail": "a@x.de", "password": "{SSHA}abc",
               "employee_type": "staff"}
    with patch("ldap_nach_db.database.get_user_by_username",
               return_value={"id": 3, "password_hash": None}), \
         patch("ldap_nach_db.database.create_user") as anlegen, \
         patch("ldap_nach_db.database.set_user_password") as setzen:
        zahlen = uebernehmen([eintrag])

    anlegen.assert_not_called()
    setzen.assert_called_once_with(3, "{SSHA}abc")
    assert zahlen["ergaenzt"] == 1


def test_an_existing_hash_is_never_overwritten():
    eintrag = {"uid": "a", "cn": "Hans", "mail": "a@x.de", "password": "{SSHA}neu",
               "employee_type": "staff"}
    with patch("ldap_nach_db.database.get_user_by_username",
               return_value={"id": 3, "password_hash": "$2b$12$schon-da"}), \
         patch("ldap_nach_db.database.set_user_password") as setzen:
        zahlen = uebernehmen([eintrag])

    setzen.assert_not_called()
    assert zahlen["uebersprungen"] == 1


def test_an_at_sign_in_the_user_name_is_refused():
    # The login field tells a mail from a name by the @, such a name would break it.
    eintrag = {"uid": "a@b", "cn": "Krumm", "mail": "x@y.de", "password": "{SSHA}x",
               "employee_type": "staff"}
    with patch("ldap_nach_db.database.get_user_by_username") as suchen:
        zahlen = uebernehmen([eintrag])

    suchen.assert_not_called()
    assert zahlen["abgelehnt"] == 1


def test_an_entry_without_a_password_is_refused():
    eintrag = {"uid": "a", "cn": "Hans", "mail": "a@x.de", "password": "",
               "employee_type": "staff"}
    with patch("ldap_nach_db.database.get_user_by_username") as suchen:
        assert uebernehmen([eintrag])["abgelehnt"] == 1
    suchen.assert_not_called()


def test_running_it_twice_changes_nothing_the_second_time():
    eintrag = {"uid": "a", "cn": "Hans", "mail": "a@x.de", "password": "{SSHA}abc",
               "employee_type": "staff"}
    with patch("ldap_nach_db.database.get_user_by_username",
               return_value={"id": 3, "password_hash": "{SSHA}abc"}), \
         patch("ldap_nach_db.database.set_user_password") as setzen:
        zahlen = uebernehmen([eintrag])
    setzen.assert_not_called()
    assert zahlen == {"angelegt": 0, "ergaenzt": 0, "uebersprungen": 1,
                      "abgelehnt": 0, "ohne_zeile": 0}


def test_a_plain_text_password_is_hashed_on_the_way_in():
    # OpenLDAP keeps userPassword as it was written, the seed file has it in the clear.
    eintrag = {"uid": "a", "cn": "Hans", "mail": "a@x.de", "password": "a",
               "employee_type": "staff"}
    with patch("ldap_nach_db.database.get_user_by_username", return_value=None), \
         patch("ldap_nach_db.database.add_to_whitelist"), \
         patch("ldap_nach_db.database.create_user", return_value=1) as anlegen:
        uebernehmen([eintrag], auch_neue=True)

    from src.features.accounts.passwords import verify_password
    hash_wert = anlegen.call_args.kwargs["password_hash"]
    assert hash_wert.startswith("$2")
    assert verify_password("a", hash_wert) is True


def test_an_unknown_hashing_scheme_is_refused():
    # {MD5} and friends would land in the column unusable, better to say so out loud.
    eintrag = {"uid": "a", "cn": "Hans", "mail": "a@x.de", "password": "{MD5}xyz",
               "employee_type": "staff"}
    with patch("ldap_nach_db.database.get_user_by_username") as suchen:
        assert uebernehmen([eintrag])["abgelehnt"] == 1
    suchen.assert_not_called()


def test_a_plain_text_password_beyond_the_bcrypt_limit_is_refused():
    eintrag = {"uid": "a", "cn": "Hans", "mail": "a@x.de", "password": "x" * 100,
               "employee_type": "staff"}
    with patch("ldap_nach_db.database.get_user_by_username") as suchen:
        assert uebernehmen([eintrag])["abgelehnt"] == 1
    suchen.assert_not_called()


def test_a_column_that_holds_no_usable_hash_is_replaced():
    # An earlier run may have written plain text there, that must not stay.
    eintrag = {"uid": "a", "cn": "Hans", "mail": "a@x.de", "password": "{SSHA}abc",
               "employee_type": "staff"}
    with patch("ldap_nach_db.database.get_user_by_username",
               return_value={"id": 3, "password_hash": "a"}), \
         patch("ldap_nach_db.database.set_user_password") as setzen:
        zahlen = uebernehmen([eintrag])

    setzen.assert_called_once_with(3, "{SSHA}abc")
    assert zahlen["ergaenzt"] == 1


def test_by_default_nothing_is_created():
    """A directory entry without a row means the account was deleted, it must not come back."""
    eintrag = {"uid": "geloescht", "cn": "Weg", "mail": "", "password": "{SSHA}abc",
               "employee_type": "user"}
    with patch("ldap_nach_db.database.get_user_by_username", return_value=None), \
         patch("ldap_nach_db.database.create_user") as anlegen:
        zahlen = uebernehmen([eintrag])

    anlegen.assert_not_called()
    assert zahlen["ohne_zeile"] == 1
    assert zahlen["angelegt"] == 0


def test_with_the_flag_a_missing_row_is_created():
    eintrag = {"uid": "neu", "cn": "Neu", "mail": "", "password": "{SSHA}abc",
               "employee_type": "user"}
    with patch("ldap_nach_db.database.get_user_by_username", return_value=None), \
         patch("ldap_nach_db.database.add_to_whitelist"), \
         patch("ldap_nach_db.database.create_user", return_value=5) as anlegen:
        zahlen = uebernehmen([eintrag], auch_neue=True)

    anlegen.assert_called_once()
    assert zahlen["angelegt"] == 1
    assert zahlen["ohne_zeile"] == 0
