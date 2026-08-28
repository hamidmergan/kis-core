"""The ways in: invite in the admin area, redeem without logging in."""

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


def test_creating_an_invite_derives_the_username_and_returns_a_token(client):
    with patch("src.routes.admin.invites.database.get_user_by_username", return_value=None), \
         patch("src.routes.admin.invites.repo.open_invite_for_email", return_value=None), \
         patch("src.routes.admin.invites.repo.create_invite", return_value=3) as anlegen:
        r = client.post(
            "/admin/invites",
            json={"email": "Max.Mustermann@th-luebeck.de", "kis_role": "staff"},
        )

    assert r.status_code == 200
    body = r.json()
    assert body["uid"] == "max.mustermann"
    assert len(body["token"]) >= 32
    assert anlegen.call_args.kwargs["email"] == "Max.Mustermann@th-luebeck.de"
    assert anlegen.call_args.kwargs["role"] == "staff"


def test_inviting_someone_who_already_has_an_account_is_refused(client):
    with patch("src.routes.admin.invites.database.get_user_by_username", return_value={"id": 4}), \
         patch("src.routes.admin.invites.repo.open_invite_for_email", return_value=None), \
         patch("src.routes.admin.invites.repo.create_invite") as anlegen:
        r = client.post(
            "/admin/invites",
            json={"email": "max.mustermann@th-luebeck.de", "kis_role": "user"},
        )

    assert r.status_code == 409
    anlegen.assert_not_called()


def test_a_second_open_invite_to_the_same_address_is_refused(client):
    with patch("src.routes.admin.invites.database.get_user_by_username", return_value=None), \
         patch("src.routes.admin.invites.repo.open_invite_for_email", return_value={"id": 2}), \
         patch("src.routes.admin.invites.repo.create_invite") as anlegen:
        r = client.post(
            "/admin/invites",
            json={"email": "max.mustermann@th-luebeck.de", "kis_role": "user"},
        )

    assert r.status_code == 409
    anlegen.assert_not_called()


def test_inviting_is_gone_when_the_switch_is_off(client):
    with patch("src.routes.admin.invites.get_settings") as settings, \
         patch("src.routes.admin.invites.repo.create_invite") as anlegen:
        settings.return_value.ldap_user_creation_enabled = False
        r = client.post(
            "/admin/invites",
            json={"email": "max.mustermann@th-luebeck.de", "kis_role": "user"},
        )

    assert r.status_code == 404
    anlegen.assert_not_called()


@pytest.mark.parametrize("email", ["keine-adresse", "!@th-luebeck.de"])
def test_an_address_without_a_usable_username_is_refused(client, email):
    with patch("src.routes.admin.invites.repo.create_invite") as anlegen:
        r = client.post("/admin/invites", json={"email": email, "kis_role": "user"})

    assert r.status_code == 400
    anlegen.assert_not_called()


def test_an_unknown_role_is_refused(client):
    with patch("src.routes.admin.invites.database.get_user_by_username", return_value=None), \
         patch("src.routes.admin.invites.database.get_custom_role", return_value=None), \
         patch("src.routes.admin.invites.repo.open_invite_for_email", return_value=None), \
         patch("src.routes.admin.invites.repo.create_invite") as anlegen:
        r = client.post(
            "/admin/invites",
            json={
                "email": "max.mustermann@th-luebeck.de",
                "kis_role": "custom",
                "custom_role_id": 99,
            },
        )

    assert r.status_code == 400
    anlegen.assert_not_called()


def test_the_list_carries_the_status_of_each_invite(client):
    from datetime import datetime, timedelta

    jetzt = datetime.now()
    zeilen = [
        {"id": 1, "email": "offen@th-luebeck.de", "uid": "offen", "role": "staff",
         "custom_role_id": None, "token": "tok1", "created_at": jetzt,
         "expires_at": jetzt + timedelta(days=1), "used_at": None},
        {"id": 2, "email": "alt@th-luebeck.de", "uid": "alt", "role": "user",
         "custom_role_id": None, "token": "tok2", "created_at": jetzt,
         "expires_at": jetzt - timedelta(days=1), "used_at": None},
    ]
    with patch("src.routes.admin.invites.repo.list_invites", return_value=zeilen):
        r = client.get("/admin/invites")

    assert r.status_code == 200
    assert [e["status"] for e in r.json()["invites"]] == ["open", "expired"]


def test_withdrawing_an_unknown_invite_is_not_found(client):
    with patch("src.routes.admin.invites.repo.delete_invite", return_value=False) as loeschen:
        r = client.delete("/admin/invites/9")
    assert r.status_code == 404
    loeschen.assert_called_once_with(9)


def test_withdrawing_an_open_invite_works(client):
    with patch("src.routes.admin.invites.repo.delete_invite", return_value=True) as loeschen:
        r = client.delete("/admin/invites/9")
    assert r.status_code == 200
    loeschen.assert_called_once_with(9)


# --- the public page -----------------------------------------------------------

def _offene_einladung(**overrides):
    from datetime import datetime, timedelta

    jetzt = datetime.now()
    zeile = {
        "id": 1,
        "token": "tok",
        "email": "max.mustermann@th-luebeck.de",
        "uid": "max.mustermann",
        "role": "staff",
        "custom_role_id": None,
        "created_by": 1,
        "created_at": jetzt,
        "expires_at": jetzt + timedelta(days=7),
        "used_at": None,
    }
    zeile.update(overrides)
    return zeile


def test_an_unknown_link_is_not_found(client):
    with patch("src.routes.invites.repo.get_invite_by_token", return_value=None):
        r = client.get("/invites/gibtsnicht")
    assert r.status_code == 404


def test_an_open_link_shows_the_address_and_the_username(client):
    with patch("src.routes.invites.repo.get_invite_by_token", return_value=_offene_einladung()):
        r = client.get("/invites/tok")

    assert r.status_code == 200
    assert r.json() == {
        "email": "max.mustermann@th-luebeck.de",
        "uid": "max.mustermann",
    }


def test_a_used_link_is_gone(client):
    from datetime import datetime

    with patch("src.routes.invites.repo.get_invite_by_token",
               return_value=_offene_einladung(used_at=datetime.now())):
        r = client.get("/invites/tok")
    assert r.status_code == 410


def test_an_expired_link_is_gone(client):
    from datetime import datetime, timedelta

    with patch("src.routes.invites.repo.get_invite_by_token",
               return_value=_offene_einladung(expires_at=datetime.now() - timedelta(days=1))):
        r = client.get("/invites/tok")
    assert r.status_code == 410


def _redeem_patches():
    """Everything redemption touches, in one grip."""
    return {
        "lesen": patch("src.routes.invites.repo.get_invite_by_token", return_value=_offene_einladung()),
        "stempeln": patch("src.routes.invites.repo.mark_invite_used", return_value=True),
        "ldap": patch("src.features.accounts.provisioning.create_ldap_user", return_value="ein-langes-passwort"),
        "whitelist": patch("src.features.accounts.provisioning.database.add_to_whitelist"),
        "anlegen": patch("src.features.accounts.provisioning.database.create_user", return_value=42),
        "rolle": patch("src.features.accounts.provisioning.database.set_user_role"),
        "sitzung": patch("src.routes.invites.get_session_store"),
    }


def test_redeeming_creates_an_active_account_and_signs_in(client):
    p = _redeem_patches()
    with p["lesen"], p["stempeln"] as stempeln, p["ldap"] as ldap_add, \
         p["whitelist"] as whitelist, p["anlegen"] as anlegen, p["rolle"], p["sitzung"] as sitzung:
        sitzung.return_value.create.return_value = "sitzungsschluessel"
        r = client.post("/invites/tok", json={"password": "ein-langes-passwort"})

    assert r.status_code == 200
    assert ldap_add.call_args.kwargs["uid"] == "max.mustermann"
    assert ldap_add.call_args.kwargs["password"] == "ein-langes-passwort"
    whitelist.assert_called_once_with("max.mustermann@th-luebeck.de")
    assert anlegen.call_args.kwargs["active"] == 1
    assert anlegen.call_args.kwargs["role"] == "staff"
    stempeln.assert_called_once_with(1)
    assert r.cookies.get("session") == "sitzungsschluessel"


def test_a_short_password_is_refused_before_anything_is_created(client):
    p = _redeem_patches()
    with p["lesen"], p["stempeln"] as stempeln, p["ldap"] as ldap_add, \
         p["whitelist"], p["anlegen"], p["rolle"], p["sitzung"]:
        r = client.post("/invites/tok", json={"password": "kurz"})

    assert r.status_code == 400
    ldap_add.assert_not_called()
    stempeln.assert_not_called()


def test_a_link_claimed_by_someone_else_does_not_create_a_second_account(client):
    p = _redeem_patches()
    with p["lesen"], p["ldap"] as ldap_add, p["whitelist"], p["anlegen"], p["rolle"], p["sitzung"], \
         patch("src.routes.invites.repo.mark_invite_used", return_value=False):
        r = client.post("/invites/tok", json={"password": "ein-langes-passwort"})

    assert r.status_code == 410
    ldap_add.assert_not_called()


def test_a_failed_account_creation_leaves_the_link_usable(client):
    from src.ldap_admin import LdapServiceError

    p = _redeem_patches()
    with p["lesen"], p["stempeln"], p["whitelist"] as whitelist, p["anlegen"], p["rolle"], p["sitzung"], \
         patch("src.features.accounts.provisioning.create_ldap_user", side_effect=LdapServiceError("weg")), \
         patch("src.routes.invites.repo.reopen_invite") as wieder_oeffnen:
        r = client.post("/invites/tok", json={"password": "ein-langes-passwort"})

    assert r.status_code == 500
    wieder_oeffnen.assert_called_once_with(1)
    whitelist.assert_not_called()


def test_an_account_that_already_exists_reports_a_conflict(client):
    from src.ldap_admin import LdapUserExistsError

    p = _redeem_patches()
    with p["lesen"], p["stempeln"], p["whitelist"], p["anlegen"], p["rolle"], p["sitzung"], \
         patch("src.features.accounts.provisioning.create_ldap_user", side_effect=LdapUserExistsError("max.mustermann")), \
         patch("src.routes.invites.repo.reopen_invite"):
        r = client.post("/invites/tok", json={"password": "ein-langes-passwort"})

    assert r.status_code == 409


def test_given_names_become_the_display_name(client):
    p = _redeem_patches()
    with p["lesen"], p["stempeln"], p["ldap"], p["whitelist"], p["anlegen"] as anlegen, \
         p["rolle"], p["sitzung"]:
        client.post("/invites/tok", json={
            "password": "ein-langes-passwort",
            "given_name": "Max",
            "surname": "Mustermann",
        })

    assert anlegen.call_args.kwargs["display_name"] == "Max Mustermann"


def test_without_a_name_the_username_is_shown(client):
    p = _redeem_patches()
    with p["lesen"], p["stempeln"], p["ldap"], p["whitelist"], p["anlegen"] as anlegen, \
         p["rolle"], p["sitzung"]:
        client.post("/invites/tok", json={"password": "ein-langes-passwort"})

    assert anlegen.call_args.kwargs["display_name"] == "max.mustermann"


# The invitation page has to be reachable without a session.

@pytest.fixture
def client_ohne_sitzung(monkeypatch):
    monkeypatch.setenv("LDAP_USER_CREATION_ENABLED", "true")
    monkeypatch.setenv("LDAP_BASE_DN", "dc=th-luebeck,dc=de")
    monkeypatch.setenv("LDAP_BIND_DN", "cn=admin,dc=th-luebeck,dc=de")
    monkeypatch.setenv("LDAP_BIND_PASSWORD", "admin")
    monkeypatch.setenv("LDAP_SERVER", "ldap://openldap")

    from src.dependencies import get_settings
    from src.app import app

    get_settings.cache_clear()
    app.dependency_overrides.clear()
    yield TestClient(app)
    app.dependency_overrides.clear()
    get_settings.cache_clear()


def test_reading_an_invite_needs_no_session(client_ohne_sitzung):
    with patch("src.routes.invites.repo.get_invite_by_token", return_value=_offene_einladung()):
        r = client_ohne_sitzung.get("/invites/tok")
    assert r.status_code == 200, "wer eingeladen wird, hat noch kein Konto"


def test_redeeming_an_invite_needs_no_session(client_ohne_sitzung):
    p = _redeem_patches()
    with p["lesen"], p["stempeln"], p["ldap"], p["whitelist"], p["anlegen"], p["rolle"], p["sitzung"] as sitzung:
        sitzung.return_value.create.return_value = "sitzungsschluessel"
        r = client_ohne_sitzung.post("/invites/tok", json={"password": "ein-langes-passwort"})
    assert r.status_code == 200


def test_the_admin_side_still_needs_a_session(client_ohne_sitzung):
    r = client_ohne_sitzung.get("/admin/invites")
    assert r.status_code == 401, "die Verwaltung bleibt zu"


def test_eight_characters_are_enough_and_seven_are_not(client):
    """The limit is deliberately eight, moving it should be noticed."""
    p = _redeem_patches()
    with p["lesen"], p["stempeln"], p["ldap"], p["whitelist"], p["anlegen"], p["rolle"], p["sitzung"] as sitzung:
        sitzung.return_value.create.return_value = "sitzungsschluessel"
        gerade_genug = client.post("/invites/tok", json={"password": "12345678"})

    p = _redeem_patches()
    with p["lesen"], p["stempeln"], p["ldap"], p["whitelist"], p["anlegen"], p["rolle"], p["sitzung"]:
        zu_kurz = client.post("/invites/tok", json={"password": "1234567"})

    assert gerade_genug.status_code == 200
    assert zu_kurz.status_code == 400
