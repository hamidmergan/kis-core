"""A switched-off course room says so and answers with 423 instead of 403."""

import asyncio
import inspect

import pytest
from fastapi import HTTPException

from src.features.ai_assistant import schemas
from src.features.ai_assistant.routes import _workspace_access
from src.features.ai_assistant.routes import workspaces as routes
from src.i18n import t

MENTOR = 1
TUTOR = 2
LERNENDER = 3
FREMDER = 4

OFFEN = {"id": 7, "uuid": "w-1", "title": "Kurs", "user_id": MENTOR, "is_active": True}
ZU = {**OFFEN, "is_active": False}


@pytest.fixture
def workspace_mit(monkeypatch):
    """Stubs out the database: which room, who is tutor, who is enrolled."""
    def einrichten(workspace, tutoren=frozenset(), eingeschrieben=frozenset()):
        monkeypatch.setattr(_workspace_access.db, "get_aia_workspace", lambda uuid: workspace)
        monkeypatch.setattr(
            _workspace_access.db, "is_workspace_tutor", lambda ws_id, uid: uid in tutoren
        )
        monkeypatch.setattr(
            _workspace_access.db, "is_student_enrolled", lambda ws_id, uid: uid in eingeschrieben
        )
    return einrichten


# --- The way in -----------------------------------------------------------

def test_lernender_kommt_nicht_in_den_abgeschalteten_raum(workspace_mit):
    """The bookmark used to slip past this and the chat kept answering."""
    workspace_mit(ZU, eingeschrieben={LERNENDER})
    with pytest.raises(HTTPException) as fehler:
        _workspace_access._require_workspace_access("w-1", LERNENDER)
    assert fehler.value.status_code == 423


def test_die_absage_sagt_woran_es_liegt(workspace_mit):
    """Without its own text it would say 'no access', and that is not true here."""
    workspace_mit(ZU, eingeschrieben={LERNENDER})
    with pytest.raises(HTTPException) as fehler:
        _workspace_access._require_workspace_access("w-1", LERNENDER, locale="de")
    assert fehler.value.detail == t("workspace.inactive", "de")
    assert fehler.value.detail != t("workspace.accessDenied", "de")


def test_eigentuemer_kommt_auch_im_abgeschalteten_raum_hinein(workspace_mit):
    workspace_mit(ZU)
    assert _workspace_access._require_workspace_access("w-1", MENTOR) == ZU


def test_tutor_kommt_auch_im_abgeschalteten_raum_hinein(workspace_mit):
    """The room is switched off exactly while tutors are setting it up."""
    workspace_mit(ZU, tutoren={TUTOR}, eingeschrieben={TUTOR})
    assert _workspace_access._require_workspace_access("w-1", TUTOR) == ZU


def test_offener_raum_bleibt_offen(workspace_mit):
    workspace_mit(OFFEN, eingeschrieben={LERNENDER})
    assert _workspace_access._require_workspace_access("w-1", LERNENDER) == OFFEN


def test_fremder_erfaehrt_weiterhin_nur_kein_zugriff(workspace_mit):
    """423 would tell an outsider that this room exists."""
    workspace_mit(ZU)
    with pytest.raises(HTTPException) as fehler:
        _workspace_access._require_workspace_access("w-1", FREMDER)
    assert fehler.value.status_code == 403


# --- Who sees the room as open --------------------------------------------

@pytest.fixture
def tutoren(monkeypatch):
    def einrichten(namen=frozenset()):
        monkeypatch.setattr(
            routes.db, "is_workspace_tutor", lambda ws_id, uid: uid in namen
        )
    return einrichten


def test_offenheit_haengt_an_der_person_nicht_nur_am_schalter(tutoren):
    tutoren({TUTOR})
    assert routes._is_open_for(ZU, LERNENDER) is False
    assert routes._is_open_for(ZU, MENTOR) is True
    assert routes._is_open_for(ZU, TUTOR) is True
    assert routes._is_open_for(OFFEN, LERNENDER) is True


# --- The way via the link -------------------------------------------------

@pytest.fixture
def beitritt(monkeypatch):
    """Joining without a database, with a log of every enrollment."""
    def einrichten(workspace, tutoren=frozenset()):
        protokoll = []
        monkeypatch.setattr(
            routes.db, "get_workspace_by_access_link_code",
            lambda code: (workspace, {"id": 22, "expires_at": None}),
        )
        monkeypatch.setattr(routes.db, "get_enrollment", lambda *a, **k: None)
        monkeypatch.setattr(
            routes.db, "is_workspace_tutor", lambda ws_id, uid: uid in tutoren
        )

        def enroll_student(workspace_id, user_id, enrolled_until, link_id=None, role="student"):
            protokoll.append((workspace_id, user_id))
            return 123

        monkeypatch.setattr(routes.db, "enroll_student", enroll_student)
        return protokoll
    return einrichten


def _beitreten(user_id=LERNENDER):
    return (
        routes.enroll(schemas.EnrollBody(enroll_code="ein-link"), {"user_id": user_id}, "de")
    )


def test_beitritt_in_den_abgeschalteten_raum_klappt_und_sagt_es(beitritt):
    """Rejecting would have sent the person looking for a link again later."""
    protokoll = beitritt(ZU)
    ergebnis = _beitreten()
    assert protokoll == [(ZU["id"], LERNENDER)]
    assert ergebnis["enrollment_id"] == 123
    assert ergebnis["is_open"] is False


def test_beitritt_in_den_offenen_raum_meldet_offen(beitritt):
    beitritt(OFFEN)
    assert _beitreten()["is_open"] is True


def test_eigener_link_fuehrt_den_eigentuemer_auch_im_zu_raum_hinein(beitritt):
    beitritt(ZU)
    ergebnis = _beitreten(user_id=MENTOR)
    assert ergebnis["enrollment_id"] is None
    assert ergebnis["is_open"] is True


def test_vorschau_sagt_vorher_ob_der_raum_offen_ist(monkeypatch):
    """Otherwise there would only be a button leading nowhere."""
    monkeypatch.setattr(
        routes.db, "get_workspace_by_access_link_code",
        lambda code: (ZU, {"id": 22, "expires_at": None}),
    )
    monkeypatch.setattr(routes.db, "is_workspace_tutor", lambda ws_id, uid: False)
    vorschau = (routes.preview_access_link("ein-link", {"user_id": LERNENDER}, "de"))
    assert vorschau["title"] == ZU["title"]
    assert vorschau["is_open"] is False


# --- The card in the list -------------------------------------------------

def test_abgeschalteter_raum_faellt_nicht_mehr_aus_der_liste():
    """If the row disappears there is nothing for the notice to hang on."""
    from src.features.ai_assistant.repository import workspaces as repo
    quelle = inspect.getsource(repo.get_aia_workspaces_for_member)
    assert "m.is_active = TRUE" not in quelle


def test_die_zeile_bringt_ihren_zustand_mit():
    """The list builds the notice from is_active, so the field has to come along."""
    from src.features.ai_assistant.routes import workspaces as routes_modul
    quelle = inspect.getsource(routes_modul.list_workspaces)
    assert '"is_active": m["is_active"]' in quelle
