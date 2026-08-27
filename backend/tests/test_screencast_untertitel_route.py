"""The browser player has to be able to fetch the subtitle file."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    from src.dependencies import get_current_user
    from src.security.auth import verify_auth
    from src.app import app

    app.dependency_overrides[verify_auth] = lambda: None
    app.dependency_overrides[get_current_user] = lambda: {"user_id": 1, "email": "a@b.de", "role": "user"}
    yield TestClient(app)
    app.dependency_overrides.clear()


_JOB = {"user_id": 1, "job_uuid": "j", "status": "success", "original_filename": "vortrag.pptx"}
_VTT = b"WEBVTT\n\n00:00:00.000 --> 00:00:02.000\nHallo\n"


def test_untertitel_kommen_als_vtt_zurueck(client):
    with patch("src.routes.jobs._download.db.get_job", return_value=_JOB), \
         patch("src.routes.jobs._download.get_job_file", return_value=_VTT):
        r = client.get("/jobs/j/subtitles")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/vtt")
    assert "Hallo" in r.text


def test_fremder_job_gibt_keine_untertitel_heraus(client):
    with patch("src.routes.jobs._download.db.get_job", return_value={**_JOB, "user_id": 99}), \
         patch("src.routes.jobs._download.get_job_file", return_value=_VTT):
        r = client.get("/jobs/j/subtitles")
    assert r.status_code == 404


def test_ohne_untertitel_gibt_es_nichts_zu_holen(client):
    with patch("src.routes.jobs._download.db.get_job", return_value=_JOB), \
         patch("src.routes.jobs._download.get_job_file", side_effect=FileNotFoundError):
        r = client.get("/jobs/j/subtitles")
    assert r.status_code == 404
