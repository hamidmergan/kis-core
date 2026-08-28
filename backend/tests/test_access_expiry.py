"""An expired test access gets neither a fresh session nor a running one."""

from datetime import datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

GESTERN = datetime.now() - timedelta(days=1)
MORGEN = datetime.now() + timedelta(days=1)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("LDAP_SERVER", "ldap://openldap")
    monkeypatch.setenv("LDAP_BASE_DN", "dc=th-luebeck,dc=de")

    from src.dependencies import get_settings
    from src.security.auth import verify_auth
    from src.app import app

    get_settings.cache_clear()
    app.dependency_overrides[verify_auth] = lambda: None
    yield TestClient(app)
    app.dependency_overrides.clear()
    get_settings.cache_clear()


def _anmelden(client, konto):
    """Logs in with LDAP and the whitelist out of the way."""
    with patch("src.routes.auth.authenticate_user", return_value={
             "username": "max.mustermann", "fullname": "Max Mustermann",
             "email": "max.mustermann@demo.kis.local", "role": "staff"}), \
         patch("src.routes.auth.database.get_user_by_username", return_value=konto), \
         patch("src.routes.auth.database.update_user"), \
         patch("src.routes.auth.database.get_setting", return_value="false"), \
         patch("src.routes.auth.get_session_store") as store:
        store.return_value = MagicMock()
        store.return_value.create.return_value = "tok"
        antwort = client.post("/auth/login", json={
            "username": "max.mustermann", "password": "geheim123",
        })
        return antwort, store.return_value.create


def test_an_expired_test_access_cannot_log_in(client):
    konto = {"id": 42, "role": "staff", "custom_role_id": None,
             "access_expires_at": GESTERN}
    antwort, anlegen = _anmelden(client, konto)

    assert antwort.status_code == 403
    assert antwort.json()["detail"] == "access_expired"
    anlegen.assert_not_called()


def test_a_running_test_access_carries_its_deadline_into_the_session(client):
    konto = {"id": 42, "role": "staff", "custom_role_id": None,
             "access_expires_at": MORGEN}
    antwort, anlegen = _anmelden(client, konto)

    assert antwort.status_code == 200
    assert anlegen.call_args.kwargs["data"]["access_expires_at"] == MORGEN.isoformat()


def test_a_normal_account_carries_no_deadline(client):
    konto = {"id": 5, "role": "admin", "custom_role_id": None, "access_expires_at": None}
    antwort, anlegen = _anmelden(client, konto)

    assert antwort.status_code == 200
    assert anlegen.call_args.kwargs["data"]["access_expires_at"] is None


class _Anfrage:
    """Just enough request for the gate."""

    def __init__(self, sitzung="tok"):
        self.url = SimpleNamespace(path="/aia/workspaces")
        self.cookies = {"session": sitzung} if sitzung else {}
        self.headers = {}


async def _torwaechter(sitzungsdaten):
    from src.security.auth import verify_auth

    store = MagicMock()
    store.get_data.return_value = sitzungsdaten
    with patch("src.security.auth.get_session_store", return_value=store), \
         patch("src.security.auth.get_settings", return_value=SimpleNamespace(is_local_mode=False)):
        return await verify_auth(_Anfrage())


@pytest.mark.asyncio
async def test_the_gate_lets_a_running_test_access_through():
    assert await _torwaechter({"user_id": 42, "access_expires_at": MORGEN.isoformat()}) is None


@pytest.mark.asyncio
async def test_the_gate_lets_a_normal_account_through():
    assert await _torwaechter({"user_id": 5, "access_expires_at": None}) is None


@pytest.mark.asyncio
async def test_the_gate_lets_an_old_session_without_the_key_through():
    assert await _torwaechter({"user_id": 5}) is None


@pytest.mark.asyncio
async def test_the_gate_throws_an_expired_test_access_out():
    with pytest.raises(HTTPException) as fehler:
        await _torwaechter({"user_id": 42, "access_expires_at": GESTERN.isoformat()})
    assert fehler.value.status_code == 403
    assert fehler.value.detail == "access_expired"
