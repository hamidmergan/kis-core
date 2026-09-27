"""The preview shows description and teacher, but no numbers."""

import asyncio

import pytest

from src.features.ai_assistant.routes import workspaces as routes

MENTOR = 1
LERNENDER = 3

MODUL = {
    "id": 7,
    "uuid": "w-1",
    "title": "WuK",
    "description": "Wirtschaft und Kommunikation, Sommersemester 2026",
    "user_id": MENTOR,
    "is_active": True,
}


@pytest.fixture
def vorschau(monkeypatch):
    """Preview without a database, either via the link or the old code."""
    def einrichten(workspace=MODUL, ablauf=None, ueber_link=True, lehrperson="Dr. Martina Voss"):
        monkeypatch.setattr(
            routes.db, "get_workspace_by_access_link_code",
            lambda code: (workspace, {"id": 22, "expires_at": ablauf}) if ueber_link else None,
        )
        monkeypatch.setattr(routes.db, "get_workspace_by_enroll_code", lambda code: workspace)
        monkeypatch.setattr(routes.db, "is_workspace_tutor", lambda ws_id, uid: False)
        monkeypatch.setattr(
            routes.db, "get_user_by_id",
            lambda uid: {"display_name": lehrperson} if lehrperson else None,
        )
        return (routes.preview_access_link("ein-link", {"user_id": LERNENDER}, "de"))
    return einrichten


def test_die_vorschau_nennt_die_beschreibung(vorschau):
    """Without it an abbreviation tells nobody what the subject is."""
    assert vorschau()["description"] == MODUL["description"]


def test_die_vorschau_nennt_die_lehrperson(vorschau):
    """The name answers who the link comes from."""
    assert vorschau()["owner_name"] == "Dr. Martina Voss"


def test_die_vorschau_nennt_den_letzten_tag(vorschau):
    """The expiry is already in the link, hiding it saves nothing."""
    from datetime import datetime
    ergebnis = vorschau(ablauf=datetime(2026, 9, 30, 12, 0, 0))
    assert ergebnis["access_until"] == "2026-09-30T12:00:00Z"


def test_ohne_ablauf_bleibt_das_feld_leer(vorschau):
    assert vorschau()["access_until"] is None


def test_ohne_beschreibung_bleibt_das_feld_leer(vorschau):
    """The description is optional, the card has to work without it too."""
    ergebnis = vorschau(workspace={**MODUL, "description": None})
    assert ergebnis["description"] is None


def test_eine_geloeschte_lehrperson_kippt_die_vorschau_nicht(vorschau):
    assert vorschau(lehrperson=None)["owner_name"] is None


def test_der_alte_code_weg_liefert_dieselben_felder(vorschau):
    """Both paths end on the same card, so both have to deliver everything."""
    ergebnis = vorschau(
        workspace={**MODUL, "enroll_code_expires": None}, ueber_link=False,
    )
    assert ergebnis["description"] == MODUL["description"]
    assert ergebnis["owner_name"] == "Dr. Martina Voss"
    assert ergebnis["access_until"] is None


def test_der_alte_code_weg_nennt_sein_eigenes_ablaufdatum(vorschau):
    """There the deadline hangs off the workspace, not off a link."""
    from datetime import datetime
    ergebnis = vorschau(
        workspace={**MODUL, "enroll_code_expires": datetime(2026, 9, 30, 12, 0, 0)},
        ueber_link=False,
    )
    assert ergebnis["access_until"] == "2026-09-30T12:00:00Z"


def test_die_vorschau_zaehlt_nichts_mit():
    """Sources and participants deliberately stay out."""
    import inspect
    quelle = inspect.getsource(routes.preview_access_link)
    assert "count" not in quelle.lower()
