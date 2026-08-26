"""Demo-Zugang: der Haken im Admin und die zwei Routen auf der Startseite."""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

ADMIN = {"user_id": 1, "email": "admin@th-luebeck.de", "role": "admin"}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ADMIN_EMAIL", "admin@th-luebeck.de")

    from src.app import app
    from src.dependencies import get_current_user, get_settings
    from src.security.auth import verify_auth

    get_settings.cache_clear()
    app.dependency_overrides[verify_auth] = lambda: None
    app.dependency_overrides[get_current_user] = lambda: ADMIN
    yield TestClient(app)
    app.dependency_overrides.clear()
    get_settings.cache_clear()


def test_der_haken_setzt_die_markierung(client):
    with patch("src.routes.admin.users.db.get_user_by_id", return_value={"id": 7}), \
         patch("src.routes.admin.users.db.set_user_demo") as setzen:
        r = client.post("/admin/users/7/demo", json={"is_demo": True})
    assert r.status_code == 200
    assert r.json()["is_demo"] is True
    setzen.assert_called_once_with(7, True)


def test_ein_unbekanntes_konto_gibt_vierhundertvier(client):
    with patch("src.routes.admin.users.db.get_user_by_id", return_value=None), \
         patch("src.routes.admin.users.db.set_user_demo") as setzen:
        r = client.post("/admin/users/999/demo", json={"is_demo": True})
    assert r.status_code == 404
    setzen.assert_not_called()


def _kurs(ws_id, uuid, joined=False, owned=False, via_demo=None,
           titel="Sustainable Energy Systems"):
    return {
        "id": ws_id, "uuid": uuid, "title": titel,
        "description": "Modul B.Eng.", "source_count": 7, "joined": joined,
        "via_demo": joined if via_demo is None else via_demo, "owned": owned,
    }


def test_die_liste_reicht_nur_die_sichtbaren_felder_durch(client):
    with patch("src.features.ai_assistant.routes.demo.db.get_demo_workspaces",
               return_value=[_kurs(5, "w5")]):
        r = client.get("/ai-assistant/demo/workspaces")
    assert r.status_code == 200
    assert r.json() == [{
        "uuid": "w5", "title": "Sustainable Energy Systems",
        "description": "Modul B.Eng.", "source_count": 7, "joined": False,
        "via_demo": False, "owned": False,
    }]
    # Die interne Kennung darf die Route nicht verlassen.
    assert "id" not in r.json()[0]


def test_ohne_angabe_wird_in_alle_offenen_eingeschrieben(client):
    kurse = [_kurs(5, "w5"), _kurs(6, "w6", joined=True), _kurs(7, "w7")]
    with patch("src.features.ai_assistant.routes.demo.db.get_demo_workspaces", return_value=kurse), \
         patch("src.features.ai_assistant.routes.demo.db.enroll_student",
               side_effect=[11, 12]) as einschreiben:
        r = client.post("/ai-assistant/demo/enroll", json={})
    assert r.status_code == 200
    assert r.json()["joined"] == ["w5", "w7"]
    assert einschreiben.call_count == 2
    einschreiben.assert_any_call(5, 1, None, via_demo=True)


def test_mit_angabe_wird_nur_dieser_eine_eingeschrieben(client):
    kurse = [_kurs(5, "w5"), _kurs(7, "w7")]
    with patch("src.features.ai_assistant.routes.demo.db.get_demo_workspaces", return_value=kurse), \
         patch("src.features.ai_assistant.routes.demo.db.enroll_student", return_value=11) as einschreiben:
        r = client.post("/ai-assistant/demo/enroll", json={"workspace_uuid": "w7"})
    assert r.json()["joined"] == ["w7"]
    einschreiben.assert_called_once_with(7, 1, None, via_demo=True)


def test_ein_fremder_kurs_gibt_vierhundertvier(client):
    with patch("src.features.ai_assistant.routes.demo.db.get_demo_workspaces",
               return_value=[_kurs(5, "w5")]), \
         patch("src.features.ai_assistant.routes.demo.db.enroll_student") as einschreiben:
        r = client.post("/ai-assistant/demo/enroll", json={"workspace_uuid": "fremd"})
    assert r.status_code == 404
    einschreiben.assert_not_called()


def test_zweimal_beitreten_legt_nichts_neues_an(client):
    with patch("src.features.ai_assistant.routes.demo.db.get_demo_workspaces",
               return_value=[_kurs(5, "w5", joined=True)]), \
         patch("src.features.ai_assistant.routes.demo.db.enroll_student") as einschreiben:
        r = client.post("/ai-assistant/demo/enroll", json={})
    assert r.json()["joined"] == []
    einschreiben.assert_not_called()


def test_verlassen_loescht_die_einschreibung(client):
    with patch("src.features.ai_assistant.routes.demo.db.get_demo_workspaces",
               return_value=[_kurs(5, "w5", joined=True)]), \
         patch("src.features.ai_assistant.routes.demo.db.delete_demo_enrollment",
               return_value=True) as loeschen:
        r = client.post("/ai-assistant/demo/leave", json={"workspace_uuid": "w5"})
    assert r.status_code == 200
    assert r.json()["left"] is True
    loeschen.assert_called_once_with(5, 1)


def test_verlassen_geht_nur_bei_demo_kursen(client):
    with patch("src.features.ai_assistant.routes.demo.db.get_demo_workspaces",
               return_value=[_kurs(5, "w5", joined=True)]), \
         patch("src.features.ai_assistant.routes.demo.db.delete_demo_enrollment") as loeschen:
        r = client.post("/ai-assistant/demo/leave", json={"workspace_uuid": "fremd"})
    assert r.status_code == 404
    loeschen.assert_not_called()


def test_verlassen_ohne_einschreibung_bleibt_ruhig(client):
    """Der Eigentuemer hat keine Einschreibung, das ist kein Fehler."""
    with patch("src.features.ai_assistant.routes.demo.db.get_demo_workspaces",
               return_value=[_kurs(5, "w5")]), \
         patch("src.features.ai_assistant.routes.demo.db.delete_demo_enrollment",
               return_value=False):
        r = client.post("/ai-assistant/demo/leave", json={"workspace_uuid": "w5"})
    assert r.status_code == 200
    assert r.json()["left"] is False


def test_der_haken_weg_raeumt_die_demo_einschreibungen_ab(client):
    """Wer den Haken verliert, dessen Demo-Teilnehmer fliegen aus dem Kurs."""
    with patch("src.routes.admin.users.db.get_user_by_id", return_value={"id": 7}), \
         patch("src.routes.admin.users.db.set_user_demo", return_value=[7]), \
         patch("src.routes.admin.users.db.delete_demo_enrollments_of_owner",
               return_value=3) as abraeumen:
        r = client.post("/admin/users/7/demo", json={"is_demo": False})
    assert r.status_code == 200
    abraeumen.assert_called_once_with(7)


def test_das_vorige_demo_konto_wird_mit_abgeraeumt(client):
    """Beim Umhaken verliert das alte Konto den Haken und damit seine Teilnehmer."""
    with patch("src.routes.admin.users.db.get_user_by_id", return_value={"id": 9}), \
         patch("src.routes.admin.users.db.set_user_demo", return_value=[7]), \
         patch("src.routes.admin.users.db.delete_demo_enrollments_of_owner",
               return_value=2) as abraeumen:
        r = client.post("/admin/users/9/demo", json={"is_demo": True})
    assert r.status_code == 200
    abraeumen.assert_called_once_with(7)


def test_beitreten_merkt_sich_den_weg_ueber_die_demo(client):
    """Sonst liesse sich spaeter nicht sagen, welche Einschreibung abgeraeumt werden darf."""
    with patch("src.features.ai_assistant.routes.demo.db.get_demo_workspaces",
               return_value=[_kurs(5, "w5")]), \
         patch("src.features.ai_assistant.routes.demo.db.enroll_student",
               return_value=11) as einschreiben:
        client.post("/ai-assistant/demo/enroll", json={})
    einschreiben.assert_called_once_with(5, 1, None, via_demo=True)


def test_der_eigentuemer_tritt_seinem_eigenen_kurs_nicht_bei(client):
    """Ihm gehoert der Kurs schon, eine Einschreibung waere sinnlos."""
    with patch("src.features.ai_assistant.routes.demo.db.get_demo_workspaces",
               return_value=[_kurs(5, "w5", owned=True)]), \
         patch("src.features.ai_assistant.routes.demo.db.enroll_student") as einschreiben:
        r = client.post("/ai-assistant/demo/enroll", json={})
    assert r.json()["joined"] == []
    einschreiben.assert_not_called()


def test_verlassen_fasst_eine_echte_einschreibung_nicht_an(client):
    """Wer ueber einen richtigen Link drin ist, bleibt drin."""
    with patch("src.features.ai_assistant.routes.demo.db.get_demo_workspaces",
               return_value=[_kurs(5, "w5", joined=True, via_demo=False)]), \
         patch("src.features.ai_assistant.routes.demo.db.delete_demo_enrollment",
               return_value=False) as loeschen:
        r = client.post("/ai-assistant/demo/leave", json={"workspace_uuid": "w5"})
    assert r.json()["left"] is False
    # Die Abfrage selbst schuetzt: sie fasst nur Zeilen mit via_demo an.
    loeschen.assert_called_once_with(5, 1)
