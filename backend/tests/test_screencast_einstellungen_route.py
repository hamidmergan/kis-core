"""Schritt 6 holt seinen Stand hier und speichert ihn hier."""

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

UUID = "1" * 32
_JOB = {"user_id": 1, "job_uuid": UUID, "status": "success"}
MODUL = "src.routes.screencast.einstellungen"


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


def _dateien(vorhanden: dict):
    def hole(user_id, job_uuid, name):
        if name not in vorhanden:
            raise FileNotFoundError(name)
        return vorhanden[name]
    return hole


def test_lesen_liefert_einstellungen_und_abzug(client):
    dateien = {
        "einstellungen.json": json.dumps({"speed": 1.1, "video_folien": [0, 2]}).encode(),
        "vertonter_stand.json": json.dumps({"scripts": ["a"], "folientexte": ["A"]}).encode(),
        "render_scripts.json": json.dumps(["a", "b", "c"]).encode(),
    }
    with patch(f"{MODUL}.get_job", return_value=_JOB), \
         patch(f"{MODUL}.get_job_file", side_effect=_dateien(dateien)), \
         patch(f"{MODUL}.get_audio_slide_count", return_value=3), \
         patch(f"{MODUL}.hat_audio_slide", side_effect=lambda u, j, i: i != 1):
        r = client.get(f"/screencast/{UUID}/vertonungs-stand")
    assert r.status_code == 200
    daten = r.json()
    assert daten["einstellungen"]["speed"] == 1.1
    assert daten["stand"]["folientexte"] == ["A"]
    assert daten["hat_ton"] == [True, False, True]


def test_ohne_gespeicherten_stand_kommt_null(client):
    with patch(f"{MODUL}.get_job", return_value=_JOB), \
         patch(f"{MODUL}.get_job_file", side_effect=_dateien({})), \
         patch(f"{MODUL}.get_audio_slide_count", return_value=0), \
         patch(f"{MODUL}.hat_audio_slide", return_value=False):
        r = client.get(f"/screencast/{UUID}/vertonungs-stand")
    assert r.status_code == 200
    assert r.json() == {"einstellungen": None, "stand": None, "hat_ton": []}


def test_fremder_auftrag_wird_nicht_verraten(client):
    with patch(f"{MODUL}.get_job", return_value={**_JOB, "user_id": 2}):
        r = client.get(f"/screencast/{UUID}/vertonungs-stand")
    assert r.status_code == 404


def test_speichern_schreibt_die_datei(client):
    with patch(f"{MODUL}.get_job", return_value=_JOB), \
         patch(f"{MODUL}.save_job_file") as sichern:
        r = client.put(f"/screencast/{UUID}/einstellungen",
                       json={"speed": 1.1, "video_folien": [0, 2], "neu_vertonen": [2]})
    assert r.status_code == 200
    assert sichern.call_args_list[0][0][2] == "einstellungen.json"
    geschrieben = json.loads(sichern.call_args_list[0][0][3].decode())
    assert geschrieben["video_folien"] == [0, 2]


def test_speichern_auf_fremdem_auftrag_wird_abgelehnt(client):
    with patch(f"{MODUL}.get_job", return_value={**_JOB, "user_id": 2}), \
         patch(f"{MODUL}.save_job_file") as sichern:
        r = client.put(f"/screencast/{UUID}/einstellungen", json={"speed": 1.0})
    assert r.status_code == 404
    assert sichern.call_count == 0


def test_kaputte_uuid_wird_abgelehnt(client):
    r = client.get("/screencast/nichtguelt/vertonungs-stand")
    assert r.status_code == 400


def test_einzelabruf_findet_die_letzte_folie_trotz_luecke(client):
    """Beim ersten Lauf mit Ausschluss hat der Ordner Luecken."""
    modul = "src.routes.screencast.audio"
    with patch(f"{modul}.get_job", return_value=_JOB), \
         patch(f"{modul}.get_audio_slide_count", return_value=9), \
         patch(f"{modul}.get_audio_slide", return_value=b"ID3"):
        r = client.get(f"/screencast/audio/{UUID}/9")
    assert r.status_code == 200
    assert r.content == b"ID3"


def test_einzelabruf_gibt_404_wenn_die_datei_fehlt(client):
    modul = "src.routes.screencast.audio"
    with patch(f"{modul}.get_job", return_value=_JOB), \
         patch(f"{modul}.get_audio_slide_count", return_value=9), \
         patch(f"{modul}.get_audio_slide", return_value=None):
        r = client.get(f"/screencast/audio/{UUID}/5")
    assert r.status_code == 404
