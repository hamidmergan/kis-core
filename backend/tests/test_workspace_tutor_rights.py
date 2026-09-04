"""Tutors manage like the owner, except inviting and promoting."""

import pytest
from fastapi import HTTPException

from src.features.ai_assistant.routes import _workspace_access

MENTOR = 1
TUTOR = 2
LERNENDER = 3
FREMDER = 4

WORKSPACE = {"id": 7, "uuid": "w-1", "user_id": MENTOR}


@pytest.fixture
def workspace_mit(monkeypatch):
    """Stubs out the database access and fixes who is a tutor."""
    def einrichten(tutoren: set[int], eingeschrieben: set[int] = frozenset()):
        monkeypatch.setattr(_workspace_access.db, "get_aia_workspace", lambda uuid: WORKSPACE)
        monkeypatch.setattr(
            _workspace_access.db, "is_workspace_tutor", lambda ws_id, uid: uid in tutoren
        )
        monkeypatch.setattr(
            _workspace_access.db, "is_student_enrolled", lambda ws_id, uid: uid in eingeschrieben
        )
    return einrichten


# --- Who may manage -------------------------------------------------------

def test_eigentuemer_darf_verwalten(workspace_mit):
    workspace_mit(tutoren=set())
    assert _workspace_access._require_workspace_manage("w-1", MENTOR) == WORKSPACE


def test_tutor_darf_verwalten(workspace_mit):
    workspace_mit(tutoren={TUTOR})
    assert _workspace_access._require_workspace_manage("w-1", TUTOR) == WORKSPACE


def test_lernender_darf_nicht_verwalten(workspace_mit):
    """Being enrolled is not enough, otherwise every participant could delete."""
    workspace_mit(tutoren=set(), eingeschrieben={LERNENDER})
    with pytest.raises(HTTPException) as fehler:
        _workspace_access._require_workspace_manage("w-1", LERNENDER)
    assert fehler.value.status_code == 403


def test_fremder_darf_nicht_verwalten(workspace_mit):
    workspace_mit(tutoren=set())
    with pytest.raises(HTTPException) as fehler:
        _workspace_access._require_workspace_manage("w-1", FREMDER)
    assert fehler.value.status_code == 403


def test_unbekannter_workspace_ist_404(monkeypatch):
    monkeypatch.setattr(_workspace_access.db, "get_aia_workspace", lambda uuid: None)
    with pytest.raises(HTTPException) as fehler:
        _workspace_access._require_workspace_manage("gibtsnicht", MENTOR)
    assert fehler.value.status_code == 404


def test_lernender_darf_weiterhin_lesen(workspace_mit):
    """The read check stays untouched, otherwise the course would be shut for everyone."""
    workspace_mit(tutoren=set(), eingeschrieben={LERNENDER})
    assert _workspace_access._require_workspace_access("w-1", LERNENDER) == WORKSPACE


def test_pruefung_kennt_den_rang_gar_nicht():
    """The check takes only a user id, no role and no permissions."""
    import inspect
    parameter = set(inspect.signature(_workspace_access._require_workspace_manage).parameters)
    assert parameter == {"workspace_uuid", "user_id", "locale"}


def test_gleiche_person_gleiche_antwort_egal_welcher_rang(workspace_mit):
    """The rank is neither in the call nor in the answer."""
    workspace_mit(tutoren=set(), eingeschrieben={LERNENDER, FREMDER})
    for konto in (LERNENDER, FREMDER):
        with pytest.raises(HTTPException) as fehler:
            _workspace_access._require_workspace_manage("w-1", konto)
        assert fehler.value.status_code == 403


# --- What stays with the owner alone --------------------------------------

def test_tutor_darf_verwalten_aber_nicht_das_unumkehrbare(workspace_mit):
    """The tutor manages everything except deleting and promoting."""
    workspace_mit(tutoren={TUTOR})
    assert _workspace_access._require_workspace_manage("w-1", TUTOR) == WORKSPACE
    with pytest.raises(HTTPException) as fehler:
        _workspace_access._require_workspace_owner("w-1", TUTOR)
    assert fehler.value.status_code == 403


def test_eigentuemer_darf_auch_das_unumkehrbare(workspace_mit):
    workspace_mit(tutoren={TUTOR})
    assert _workspace_access._require_workspace_owner("w-1", MENTOR) == WORKSPACE


def test_loeschroute_haengt_an_der_eigentuemerpruefung():
    """Otherwise a tutor could throw the workspace away with everything in it."""
    import inspect
    from src.features.ai_assistant.routes import workspaces as routes
    quelle = inspect.getsource(routes.delete_workspace)
    assert "_require_workspace_owner" in quelle
    assert "_require_workspace_manage" not in quelle


def test_beitritt_immer_als_lernender(monkeypatch):
    """Every link enrolls as a learner, no link gives away permissions."""
    from src.features.ai_assistant.repository import enrollments

    gespeichert = {}

    class FakeCursor:
        def execute(self, sql, params):
            gespeichert["sql"] = sql
            gespeichert["params"] = params
        def fetchone(self):
            return (99,)
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    class FakeConn:
        def cursor(self, *a, **k):
            return FakeCursor()
        def commit(self):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    monkeypatch.setattr(enrollments, "get_connection", lambda: FakeConn())

    enrollments.enroll_student(7, LERNENDER, None, link_id=6)
    # The role sits in the role column, behind workspace, user, link and deadline.
    assert gespeichert["params"][4] == "student"


def test_befoerdern_erfasst_alle_einschreibungen(monkeypatch):
    """Whoever is in through two links is promoted as a person, not per link."""
    from src.features.ai_assistant.repository import enrollments

    gespeichert = {}

    class FakeCursor:
        rowcount = 2
        def execute(self, sql, params):
            gespeichert["sql"] = " ".join(sql.split())
            gespeichert["params"] = params
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    class FakeConn:
        def cursor(self, *a, **k):
            return FakeCursor()
        def commit(self):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *a):
            return False

    monkeypatch.setattr(enrollments, "get_connection", lambda: FakeConn())

    geaendert = enrollments.set_participant_role(7, TUTOR, "tutor")
    assert geaendert == 2
    assert "link_id" not in gespeichert["sql"]
    assert gespeichert["params"] == ("tutor", 7, TUTOR)


# --- Storage location of uploaded files -----------------------------------

def test_datei_landet_beim_eigentuemer(lokal):
    """If the tutor uploads, the file still sits in the owner's folder."""
    from src import storage

    schluessel = storage.aia_source_key(MENTOR, "w-1", "q1", ".pdf")
    assert f"users/{MENTOR}/" in schluessel
    assert f"users/{TUTOR}/" not in schluessel

    # With the uploader's id a second folder would appear.
    falsch = storage.aia_source_key(TUTOR, "w-1", "q1", ".pdf")
    assert falsch != schluessel
    assert storage.aia_workspace_prefix(MENTOR, "w-1") not in falsch


# --- The system rank opens no foreign workspace ------------------------------

def test_admin_ohne_verwaltungsrecht_kommt_gar_nicht_rein(workspace_mit, monkeypatch):
    """The system rank opens no foreign workspace, and that stays."""
    import asyncio

    from src.features.ai_assistant import schemas
    from src.features.ai_assistant.routes import workspaces as routes

    workspace_mit(tutoren={TUTOR})
    geschrieben: list = []
    monkeypatch.setattr(routes.db, "update_aia_workspace", lambda *a, **k: geschrieben.append(a))
    with pytest.raises(HTTPException) as fehler:
        asyncio.run(
            routes.patch_workspace(
                "w-1",
                schemas.PatchWorkspaceBody(title="Neu"),
                current_user={"user_id": FREMDER, "role": "admin", "email": ""},
                locale="de",
            )
        )
    assert fehler.value.status_code == 403
    assert geschrieben == []
