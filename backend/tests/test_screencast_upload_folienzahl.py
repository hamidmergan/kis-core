"""Eine korrigierte PPTX mit anderer Folienzahl verschoebe Skripte und Ton."""

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

UUID = "f" * 32
_JOB = {"user_id": 1, "job_uuid": UUID, "status": "awaiting_user"}
_PPTX = b"PK\x03\x04" + b"0" * 200


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


def _hochladen(client, neue_texte, alte_anzahl=3, mit_job=True):
    modul = "src.routes.screencast.translate"
    alt = json.dumps(["alt"] * alte_anzahl).encode()
    with patch(f"{modul}.validate_or_raise"), \
         patch(f"{modul}.db.get_job", return_value=_JOB), \
         patch(f"{modul}.extract_text_per_slide", return_value=neue_texte), \
         patch(f"{modul}.get_job_file", return_value=alt), \
         patch(f"{modul}.save_job_file_from_path"), \
         patch(f"{modul}.save_job_file") as sichern, \
         patch(f"{modul}.convert_slides_to_images_async", return_value=[]), \
         patch(f"{modul}.maybe_start_cleanup_task"), \
         patch(f"{modul}._enforce_queue_and_quota"), \
         patch(f"{modul}.db.create_job"), \
         patch(f"{modul}.db.update_job_status"):
        daten = {"translate_job_uuid": UUID} if mit_job else {}
        r = client.post(
            "/screencast/upload-corrected",
            files={"file": ("a.pptx", _PPTX, "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
            data=daten,
        )
    return r, sichern


def test_gleiche_anzahl_geht_durch(client):
    r, _ = _hochladen(client, ["a", "b", "c"])
    assert r.status_code == 200


def test_eine_folie_weniger_wird_abgelehnt(client):
    r, _ = _hochladen(client, ["a", "b"])
    assert r.status_code == 400
    assert "3" in r.json()["detail"] and "2" in r.json()["detail"]


def test_eine_folie_mehr_wird_abgelehnt(client):
    r, _ = _hochladen(client, ["a", "b", "c", "d"])
    assert r.status_code == 400


def test_bei_ablehnung_wird_nichts_geschrieben(client):
    modul = "src.routes.screencast.translate"
    with patch(f"{modul}.validate_or_raise"), \
         patch(f"{modul}.db.get_job", return_value=_JOB), \
         patch(f"{modul}.extract_text_per_slide", return_value=["a"]), \
         patch(f"{modul}.get_job_file", return_value=json.dumps(["alt"] * 3).encode()), \
         patch(f"{modul}.save_job_file_from_path") as ablegen, \
         patch(f"{modul}.save_job_file") as sichern, \
         patch(f"{modul}.convert_slides_to_images_async", return_value=[]), \
         patch(f"{modul}.maybe_start_cleanup_task"):
        client.post(
            "/screencast/upload-corrected",
            files={"file": ("a.pptx", _PPTX, "application/vnd.openxmlformats-officedocument.presentationml.presentation")},
            data={"translate_job_uuid": UUID},
        )
    assert ablegen.call_count == 0
    assert sichern.call_count == 0


def test_ohne_auftrag_gibt_es_keinen_bezugspunkt(client):
    """Der Einstieg ohne Uebersetzung hat nichts zum Vergleichen."""
    r, _ = _hochladen(client, ["a", "b", "c", "d", "e"], mit_job=False)
    assert r.status_code == 200


def test_der_neue_folientext_landet_in_scripts_txt(client):
    r, sichern = _hochladen(client, ["neu a", "neu b", "neu c"])
    assert r.status_code == 200
    geschrieben = json.loads(
        next(c[0][3] for c in sichern.call_args_list if c[0][2] == "scripts.txt").decode()
    )
    assert geschrieben == ["neu a", "neu b", "neu c"]


def test_gleiche_folienzahl_wirft_die_vertonung_weg(client):
    """Neue Folien unter altem Ton waeren falsch, der Vorrat muss weg."""
    modul = "src.routes.screencast.translate"
    with patch(f"{modul}.vertonung_verwerfen") as verwerfen:
        r, _ = _hochladen(client, ["a", "b", "c"])
    assert r.status_code == 200
    verwerfen.assert_called_once_with(1, UUID)


def test_abgelehnte_folienzahl_wirft_die_vertonung_nicht_weg(client):
    """Der wichtigste Test: eine abgelehnte Datei darf keinen Datenverlust anrichten."""
    modul = "src.routes.screencast.translate"
    with patch(f"{modul}.vertonung_verwerfen") as verwerfen:
        r, _ = _hochladen(client, ["a", "b"])
    assert r.status_code == 400
    verwerfen.assert_not_called()
