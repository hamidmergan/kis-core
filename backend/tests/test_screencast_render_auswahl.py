"""Die Route prueft die Auswahl, bevor sie irgendetwas in die Warteschlange legt."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

UUID = "e" * 32
_JOB = {"user_id": 1, "job_uuid": UUID, "status": "awaiting_user", "original_filename": "a.pptx"}


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


def _senden(client, **extra):
    rumpf = {
        "scripts": ["eins", "zwei", "drei"],
        "translate_job_uuid": UUID,
        "provider_id": 1,
        **extra,
    }
    modul = "src.routes.screencast.render"
    with patch(f"{modul}.db.get_job", return_value=_JOB), \
         patch(f"{modul}.job_file_exists", return_value=True), \
         patch(f"{modul}.save_job_file") as sichern, \
         patch(f"{modul}.save_result_meta"), \
         patch(f"{modul}.load_result_meta", return_value={}), \
         patch(f"{modul}.get_job_file", side_effect=FileNotFoundError), \
         patch(f"{modul}.clear_render_cache"), \
         patch(f"{modul}.db.transition_job_to_queued", return_value=True), \
         patch("src.tasks.screencast_tasks.dispatch_next_screencast_job_for_user"):
        return client.post("/screencast/render", json=rumpf), sichern


def test_leere_auswahl_wird_abgelehnt(client):
    r, _ = _senden(client, video_folien=[])
    assert r.status_code == 400


def test_folie_ausserhalb_des_bereichs_wird_abgelehnt(client):
    r, _ = _senden(client, video_folien=[0, 7])
    assert r.status_code == 400


def test_neu_vertonen_ausserhalb_des_bereichs_wird_abgelehnt(client):
    r, _ = _senden(client, neu_vertonen=[-1])
    assert r.status_code == 400


def test_gueltige_auswahl_landet_in_den_warteschlangen_parametern(client):
    r, sichern = _senden(client, video_folien=[0, 2], neu_vertonen=[2])
    assert r.status_code == 200
    import json
    params = next(
        json.loads(c[0][3].decode())
        for c in sichern.call_args_list if c[0][2] == "queue_params.json"
    )
    assert params["video_folien"] == [0, 2]
    assert params["neu_vertonen"] == [2]


def test_ohne_angabe_bleibt_die_auswahl_leer(client):
    r, sichern = _senden(client)
    assert r.status_code == 200
    import json
    params = next(
        json.loads(c[0][3].decode())
        for c in sichern.call_args_list if c[0][2] == "queue_params.json"
    )
    assert params["video_folien"] is None


def test_die_zeichengrenze_zaehlt_nur_die_gewaehlten_folien(client):
    from src.utils.file_validation import SCREENCAST_MAX_CHARS
    lang = "x" * (SCREENCAST_MAX_CHARS - 10)
    rumpf = {
        "scripts": ["kurz", lang],
        "translate_job_uuid": UUID,
        "provider_id": 1,
        "video_folien": [0],
    }
    modul = "src.routes.screencast.render"
    with patch(f"{modul}.db.get_job", return_value=_JOB), \
         patch(f"{modul}.job_file_exists", return_value=True), \
         patch(f"{modul}.save_job_file"), \
         patch(f"{modul}.save_result_meta"), \
         patch(f"{modul}.load_result_meta", return_value={}), \
         patch(f"{modul}.get_job_file", side_effect=FileNotFoundError), \
         patch(f"{modul}.clear_render_cache"), \
         patch(f"{modul}.db.transition_job_to_queued", return_value=True), \
         patch("src.tasks.screencast_tasks.dispatch_next_screencast_job_for_user"):
        r = client.post("/screencast/render", json=rumpf)
    assert r.status_code == 200
