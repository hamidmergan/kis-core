"""Der Sprung aus der Jobs-Liste muss auch waehrend der Vertonung und danach gehen."""

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

UUID = "a" * 32


@pytest.fixture
def client():
    from src.dependencies import get_current_user
    from src.dependencies_rbac import get_user_permissions
    from src.permissions import resolve_user_permissions
    from src.security.auth import verify_auth
    from src.app import app

    app.dependency_overrides[verify_auth] = lambda: None
    app.dependency_overrides[get_current_user] = lambda: {"user_id": 1, "email": "a@b.de", "role": "user"}
    app.dependency_overrides[get_user_permissions] = lambda: resolve_user_permissions("admin", None, True)
    yield TestClient(app)
    app.dependency_overrides.clear()


def _job(status: str) -> dict:
    return {
        "user_id": 1,
        "job_uuid": UUID,
        "status": status,
        "tool": "screencast_translate",
        "original_filename": "vortrag.pptx",
        "result_path": None,
    }


def _dateien(dispatch_as: str = "render", scripts_txt: bool = True):
    """Ersetzt den Job-Ordner: liefert je Dateiname den passenden Inhalt."""
    inhalt = {
        "prompt.txt": b"Sprich locker.",
        "accepted_scripts.json": json.dumps(["Folie eins", "Folie zwei"]).encode(),
        "queue_params.json": json.dumps({"dispatch_as": dispatch_as}).encode(),
    }
    if scripts_txt:
        inhalt["scripts.txt"] = json.dumps(["Text eins", "Text zwei"]).encode()

    def lesen(_user_id, _uuid, filename):
        if filename not in inhalt:
            raise FileNotFoundError(filename)
        return inhalt[filename]

    return lesen


def _hole(client, status: str, **kwargs):
    with patch("src.routes.screencast.resume.db.get_job", return_value=_job(status)), \
         patch("src.routes.screencast.resume.get_job_file", side_effect=_dateien(**kwargs)):
        return client.get(f"/screencast/resume/{UUID}")


def test_laufende_vertonung_landet_auf_der_warteseite(client):
    r = _hole(client, "running")
    assert r.status_code == 200
    assert r.json()["step"] == "rendering"


def test_eingereihte_vertonung_landet_auch_auf_der_warteseite(client):
    r = _hole(client, "queued")
    assert r.status_code == 200
    assert r.json()["step"] == "rendering"


def test_laufende_uebersetzung_bleibt_zu(client):
    r = _hole(client, "running", dispatch_as="translate")
    assert r.status_code == 409


def test_fertiger_screencast_landet_auf_fertig(client):
    r = _hole(client, "success")
    assert r.status_code == 200
    assert r.json()["step"] == "done"


def test_fertiger_screencast_geht_auch_ohne_folientexte(client):
    r = _hole(client, "success", scripts_txt=False)
    assert r.status_code == 200
    assert r.json()["step"] == "done"
    assert r.json()["slide_texts"] == []


def test_warten_auf_eingabe_bleibt_wie_gehabt(client):
    r = _hole(client, "awaiting_user")
    assert r.status_code == 200
    assert r.json()["step"] == "tts-settings"


def test_ohne_folientexte_bleibt_die_eingabe_gesperrt(client):
    r = _hole(client, "awaiting_user", scripts_txt=False)
    assert r.status_code == 404
