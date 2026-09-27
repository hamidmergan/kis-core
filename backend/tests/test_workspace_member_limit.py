"""A workspace stops taking new members once it holds AIA_WORKSPACE_MAX_MEMBERS."""

import asyncio

import pytest
from fastapi import HTTPException

from src.features.ai_assistant import schemas
from src.features.ai_assistant.routes import workspaces as routes
from src.limits import AIA_WORKSPACE_MAX_MEMBERS

MENTOR = 1
LERNENDER = 3

WORKSPACE = {"id": 7, "uuid": "w-1", "title": "Kurs", "user_id": MENTOR}
LINK = {"id": 22, "expires_at": None}


def _beitreten(user_id=LERNENDER):
    return (
        routes.enroll(
            schemas.EnrollBody(enroll_code="der-code"),
            {"user_id": user_id},
            "de",
        )
    )


@pytest.fixture
def ueber_link(monkeypatch):
    """New access-link path: nobody enrolled yet, count is stubbed."""
    protokoll = {"eingeschrieben": []}

    def einrichten(anzahl):
        monkeypatch.setattr(
            routes.db, "get_workspace_by_access_link_code",
            lambda code: (WORKSPACE, LINK),
        )
        monkeypatch.setattr(routes.db, "get_enrollment", lambda *a, **k: None)
        monkeypatch.setattr(routes.db, "count_enrollments", lambda workspace_id: anzahl)

        def enroll_student(workspace_id, user_id, enrolled_until, link_id=None, role="student"):
            protokoll["eingeschrieben"].append((workspace_id, user_id))
            return 123

        monkeypatch.setattr(routes.db, "enroll_student", enroll_student)
        return protokoll

    return einrichten


def test_voller_workspace_blockt_den_beitritt(ueber_link):
    protokoll = ueber_link(anzahl=AIA_WORKSPACE_MAX_MEMBERS)
    with pytest.raises(HTTPException) as exc:
        _beitreten()
    assert exc.value.status_code == 409
    assert protokoll["eingeschrieben"] == []


def test_platz_frei_laesst_weiterhin_beitreten(ueber_link):
    protokoll = ueber_link(anzahl=AIA_WORKSPACE_MAX_MEMBERS - 1)
    ergebnis = _beitreten()
    assert protokoll["eingeschrieben"] == [(WORKSPACE["id"], LERNENDER)]
    assert ergebnis["enrollment_id"] == 123


@pytest.fixture
def ueber_legacy_code(monkeypatch):
    """Old path: enroll_code sits directly on the workspace row."""
    protokoll = {"eingeschrieben": []}

    def einrichten(anzahl):
        monkeypatch.setattr(routes.db, "get_workspace_by_access_link_code", lambda code: None)
        monkeypatch.setattr(routes.db, "get_workspace_by_enroll_code", lambda code: WORKSPACE)
        monkeypatch.setattr(routes.db, "is_student_enrolled", lambda *a, **k: False)
        monkeypatch.setattr(routes.db, "count_enrollments", lambda workspace_id: anzahl)

        def enroll_student(workspace_id, user_id, enrolled_until):
            protokoll["eingeschrieben"].append((workspace_id, user_id))

        monkeypatch.setattr(routes.db, "enroll_student", enroll_student)
        return protokoll

    return einrichten


def test_legacy_pfad_wird_ebenfalls_begrenzt(ueber_legacy_code):
    protokoll = ueber_legacy_code(anzahl=AIA_WORKSPACE_MAX_MEMBERS)
    with pytest.raises(HTTPException) as exc:
        _beitreten()
    assert exc.value.status_code == 409
    assert protokoll["eingeschrieben"] == []
