"""Die Vorschau hinter einem Einschreibelink zeigt, worauf man klickt.

Bisher kamen nur Titel und der Schalterzustand zurueck. Der Titel ist in der
Praxis eine Abkuerzung wie "WuK", also stand vor der Einschreibung nirgends,
um welches Fach es geht und wer es fuehrt. Beschreibung und Name der
Lehrperson liegen laengst in der Datenbank, sie wurden nur nie mitgeschickt.

Zahlen bleiben bewusst draussen: wie viele Quellen und wie viele
Teilnehmende drinstecken, geht Aussenstehende nichts an.
"""

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
    """Vorschau ohne Datenbank, wahlweise ueber den Link oder den alten Code."""
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
        return asyncio.run(routes.preview_access_link("ein-link", {"user_id": LERNENDER}, "de"))
    return einrichten


def test_die_vorschau_nennt_die_beschreibung(vorschau):
    """Ohne sie sagt "WuK" niemandem, um welches Fach es geht."""
    assert vorschau()["description"] == MODUL["description"]


def test_die_vorschau_nennt_die_lehrperson(vorschau):
    """Der Name beantwortet, von wem der Link kommt."""
    assert vorschau()["owner_name"] == "Dr. Martina Voss"


def test_die_vorschau_nennt_den_letzten_tag(vorschau):
    """Das Ablaufdatum steckt schon im Link, es zu verschweigen spart nichts."""
    from datetime import datetime
    ergebnis = vorschau(ablauf=datetime(2026, 9, 30, 12, 0, 0))
    assert ergebnis["access_until"] == "2026-09-30T12:00:00Z"


def test_ohne_ablauf_bleibt_das_feld_leer(vorschau):
    assert vorschau()["access_until"] is None


def test_ohne_beschreibung_bleibt_das_feld_leer(vorschau):
    """Die Beschreibung ist freiwillig, die Karte muss auch ohne sie tragen."""
    ergebnis = vorschau(workspace={**MODUL, "description": None})
    assert ergebnis["description"] is None


def test_eine_geloeschte_lehrperson_kippt_die_vorschau_nicht(vorschau):
    assert vorschau(lehrperson=None)["owner_name"] is None


def test_der_alte_code_weg_liefert_dieselben_felder(vorschau):
    """Beide Wege enden auf derselben Karte, also muessen beide alles liefern."""
    ergebnis = vorschau(
        workspace={**MODUL, "enroll_code_expires": None}, ueber_link=False,
    )
    assert ergebnis["description"] == MODUL["description"]
    assert ergebnis["owner_name"] == "Dr. Martina Voss"
    assert ergebnis["access_until"] is None


def test_der_alte_code_weg_nennt_sein_eigenes_ablaufdatum(vorschau):
    """Dort haengt die Frist am Workspace, nicht an einem Link."""
    from datetime import datetime
    ergebnis = vorschau(
        workspace={**MODUL, "enroll_code_expires": datetime(2026, 9, 30, 12, 0, 0)},
        ueber_link=False,
    )
    assert ergebnis["access_until"] == "2026-09-30T12:00:00Z"


def test_die_vorschau_zaehlt_nichts_mit():
    """Quellen und Teilnehmende bleiben absichtlich draussen."""
    import inspect
    quelle = inspect.getsource(routes.preview_access_link)
    assert "count" not in quelle.lower()
