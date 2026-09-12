"""With several demo modules the owner marks the one the guided tour runs in."""

import asyncio

import pytest
from fastapi import HTTPException

from src.features.ai_assistant import schemas
from src.features.ai_assistant.routes import workspaces as routes

MENTOR = 1
FREMDER = 4

DEMO_WORKSPACE = {"id": 7, "uuid": "w-demo", "user_id": MENTOR, "title": "Projektmanagement",
                  "description": None, "is_active": True}


@pytest.fixture
def modul(monkeypatch):
    """Stubs the access check and the writes, and reports what was written."""
    def einrichten(besitzer_ist_demo: bool):
        geschrieben: list = []
        monkeypatch.setattr(routes, "_require_workspace_manage", lambda uuid, uid, locale=None: DEMO_WORKSPACE)
        monkeypatch.setattr(routes.db, "update_aia_workspace", lambda *a, **k: None)
        monkeypatch.setattr(routes.db, "get_user_by_id", lambda uid: {"id": uid, "is_demo": besitzer_ist_demo})
        monkeypatch.setattr(routes.db, "set_aia_workspace_tour_module",
                            lambda uuid, an: geschrieben.append((uuid, an)))
        return geschrieben
    return einrichten


def _patch(body):
    return asyncio.run(
        routes.patch_workspace(
            "w-demo", body,
            current_user={"user_id": MENTOR, "role": "user", "email": ""},
            locale="de",
        )
    )


def test_der_haken_setzt_das_rundgang_modul(modul):
    geschrieben = modul(besitzer_ist_demo=True)
    _patch(schemas.PatchWorkspaceBody(is_tour_module=True))
    assert geschrieben == [("w-demo", True)]


def test_der_haken_laesst_sich_wieder_loesen(modul):
    geschrieben = modul(besitzer_ist_demo=True)
    _patch(schemas.PatchWorkspaceBody(is_tour_module=False))
    assert geschrieben == [("w-demo", False)]


def test_ohne_haken_im_koerper_bleibt_die_markierung_unberuehrt(modul):
    geschrieben = modul(besitzer_ist_demo=True)
    _patch(schemas.PatchWorkspaceBody(title="Neu"))
    assert geschrieben == []


def test_ein_modul_ausserhalb_der_demo_nimmt_den_haken_nicht(modul):
    """Only a demo account's module can be the tour module, the tour shows nothing else."""
    geschrieben = modul(besitzer_ist_demo=False)
    with pytest.raises(HTTPException) as fehler:
        _patch(schemas.PatchWorkspaceBody(is_tour_module=True))
    assert fehler.value.status_code == 400
    assert geschrieben == []
