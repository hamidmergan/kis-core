"""Integration tests for RBAC FastAPI dependencies."""
import pytest
from fastapi import FastAPI, Depends
from fastapi.testclient import TestClient

from src.dependencies_rbac import require_admin, require_tool_access, get_user_permissions
from src.permissions import Permissions, permissions_for_system_role


def _build_client(perms: Permissions) -> TestClient:
    app = FastAPI()

    @app.get("/admin", dependencies=[Depends(require_admin)])
    def admin_route():
        return {"ok": True}

    @app.get("/translate", dependencies=[Depends(require_tool_access("translation"))])
    def tool_route():
        return {"ok": True}

    async def _override():
        return perms

    app.dependency_overrides[get_user_permissions] = _override
    return TestClient(app)


@pytest.fixture
def user_client():
    return _build_client(permissions_for_system_role("user"))


@pytest.fixture
def staff_client():
    return _build_client(permissions_for_system_role("staff"))


@pytest.fixture
def admin_client():
    return _build_client(permissions_for_system_role("admin"))


def test_user_blocked_from_admin(user_client):
    r = user_client.get("/admin")
    assert r.status_code == 403


def test_staff_allowed_in_admin_for_its_own_numbers(staff_client):
    r = staff_client.get("/admin")
    assert r.status_code == 200


def test_admin_allowed(admin_client):
    r = admin_client.get("/admin")
    assert r.status_code == 200


def test_user_blocked_from_tool(user_client):
    r = user_client.get("/translate")
    assert r.status_code == 403


def test_staff_allowed_for_tool(staff_client):
    r = staff_client.get("/translate")
    assert r.status_code == 200


def test_global_abgeschaltetes_werkzeug_ist_gesperrt(monkeypatch, staff_client):
    """Der Admin-Schalter muss auch die Route sperren, nicht nur das Menue."""
    from src import dependencies_rbac
    monkeypatch.setattr(dependencies_rbac, "is_released_now", lambda key: False)
    r = staff_client.get("/translate")
    assert r.status_code == 403


def test_frei_gegebenes_werkzeug_bleibt_offen(monkeypatch, staff_client):
    from src import dependencies_rbac
    monkeypatch.setattr(dependencies_rbac, "is_released_now", lambda key: True)
    r = staff_client.get("/translate")
    assert r.status_code == 200
