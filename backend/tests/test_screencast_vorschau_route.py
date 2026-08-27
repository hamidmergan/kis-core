"""The audio of an already voiced slide has to be fetchable while the rest runs."""

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


_JOB = {"user_id": 1, "job_uuid": UUID, "status": "running"}


def _dateien(vorhanden: dict):
    def hole(user_id, job_uuid, name):
        if name not in vorhanden:
            raise FileNotFoundError(name)
        return vorhanden[name]
    return hole


def test_ton_kommt_aus_dem_vorrat(client):
    with patch("src.routes.screencast.audio.get_job", return_value=_JOB), \
         patch("src.routes.screencast.audio.get_job_file",
               side_effect=_dateien({"render_cache/slide_003.mp3": b"ID3vorrat"})):
        r = client.get(f"/screencast/{UUID}/vorschau/3")
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/mpeg"
    assert r.content == b"ID3vorrat"


def test_nach_dem_erfolg_kommt_der_ton_aus_dem_audio_ordner(client):
    """clear_render_cache clears the cache, the same route has to keep delivering."""
    with patch("src.routes.screencast.audio.get_job", return_value={**_JOB, "status": "success"}), \
         patch("src.routes.screencast.audio.get_job_file",
               side_effect=_dateien({"audio/slide_003.mp3": b"ID3fertig"})):
        r = client.get(f"/screencast/{UUID}/vorschau/3")
    assert r.status_code == 200
    assert r.content == b"ID3fertig"


def test_der_ton_wird_nie_zwischengespeichert(client):
    """After a voice change a different voice sits under the same address."""
    with patch("src.routes.screencast.audio.get_job", return_value=_JOB), \
         patch("src.routes.screencast.audio.get_job_file",
               side_effect=_dateien({"render_cache/slide_000.mp3": b"ID3"})):
        r = client.get(f"/screencast/{UUID}/vorschau/0")
    assert r.headers["cache-control"] == "no-store"


def test_fremder_job_gibt_keinen_ton_heraus(client):
    with patch("src.routes.screencast.audio.get_job", return_value={**_JOB, "user_id": 99}), \
         patch("src.routes.screencast.audio.get_job_file",
               side_effect=_dateien({"render_cache/slide_003.mp3": b"ID3"})):
        r = client.get(f"/screencast/{UUID}/vorschau/3")
    assert r.status_code == 404


def test_folie_ohne_ton_gibt_404(client):
    with patch("src.routes.screencast.audio.get_job", return_value=_JOB), \
         patch("src.routes.screencast.audio.get_job_file", side_effect=_dateien({})):
        r = client.get(f"/screencast/{UUID}/vorschau/2")
    assert r.status_code == 404


def test_unsinnige_foliennummer_gibt_404(client):
    with patch("src.routes.screencast.audio.get_job", return_value=_JOB), \
         patch("src.routes.screencast.audio.get_job_file", side_effect=_dateien({})):
        r = client.get(f"/screencast/{UUID}/vorschau/-1")
    assert r.status_code == 404
