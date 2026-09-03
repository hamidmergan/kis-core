"""The detail payload says whether this is the demo course, the preview toggle hangs on it."""

import asyncio

import pytest

from src.features.ai_assistant.routes import _workspace_access
from src.features.ai_assistant.routes import workspaces as routes

OWNER = 1
TESTER = 3
DEMO_OWNER = 19

KURS = {
    "id": 7, "uuid": "w-1", "title": "Projektmanagement", "description": None,
    "user_id": DEMO_OWNER, "is_active": True, "status": "ready",
    "transcript_target_lang": "en", "created_at": None,
    "staff_note_text": None, "staff_note_links": [], "enroll_code": None,
    "enroll_code_expires": None,
}


@pytest.fixture
def kurs_mit(monkeypatch):
    """Stubs every database call the detail route makes."""
    def einrichten(workspace, *, demo_konto: bool, eingeschrieben=frozenset()):
        monkeypatch.setattr(_workspace_access.db, "get_aia_workspace", lambda uuid: workspace)
        monkeypatch.setattr(_workspace_access.db, "is_workspace_tutor", lambda ws_id, uid: False)
        monkeypatch.setattr(
            _workspace_access.db, "is_student_enrolled", lambda ws_id, uid: uid in eingeschrieben
        )
        monkeypatch.setattr(routes.db, "is_workspace_tutor", lambda ws_id, uid: False)
        monkeypatch.setattr(routes.db, "touch_aia_workspace_visited", lambda uuid: None)
        monkeypatch.setattr(routes.db, "get_aia_sources_by_workspace", lambda ws_id: [])
        monkeypatch.setattr(routes.db, "get_aia_chapters_by_workspace", lambda ws_id: [])
        monkeypatch.setattr(routes.db, "get_access_links_by_workspace", lambda ws_id: [])
        monkeypatch.setattr(routes.db, "is_language_training_enabled_globally", lambda: False)
        monkeypatch.setattr(routes.db, "is_language_training_active", lambda ws_id: False)
        monkeypatch.setattr(routes.db, "get_setting", lambda key, default=None: default)
        monkeypatch.setattr(
            routes.db, "get_user_by_id",
            lambda uid: {"id": uid, "is_demo": demo_konto},
        )
    return einrichten


def _abrufen(user_id: int) -> dict:
    return asyncio.run(routes.get_workspace("w-1", {"user_id": user_id}, "de"))


def test_demo_kurs_ist_als_solcher_erkennbar(kurs_mit):
    """Without this flag the tester never gets the preview toggle offered."""
    kurs_mit(KURS, demo_konto=True, eingeschrieben={TESTER})
    assert _abrufen(TESTER)["is_demo_workspace"] is True


def test_normaler_kurs_ist_kein_demo_kurs(kurs_mit):
    kurs_mit({**KURS, "user_id": OWNER}, demo_konto=False, eingeschrieben={TESTER})
    assert _abrufen(TESTER)["is_demo_workspace"] is False


def test_der_eigentuemer_sieht_die_markierung_auch(kurs_mit):
    """The demo account itself opens its own course, the flag stays true."""
    kurs_mit(KURS, demo_konto=True)
    assert _abrufen(DEMO_OWNER)["is_demo_workspace"] is True
