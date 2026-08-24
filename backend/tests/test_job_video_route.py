"""Das fertige Video muss sofort starten und springen koennen."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

UUID = "a" * 32


@pytest.fixture
def client():
    from src.dependencies import get_current_user
    from src.security.auth import verify_auth
    from src.app import app

    app.dependency_overrides[verify_auth] = lambda: None
    app.dependency_overrides[get_current_user] = lambda: {"user_id": 1, "email": "a@b.de", "role": "user"}
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def video(tmp_path):
    pfad = tmp_path / "screencast.mp4"
    pfad.write_bytes(bytes(range(256)) * 8)
    return pfad


def _job(pfad, **kwargs):
    return {"user_id": 1, "job_uuid": UUID, "status": "success",
            "result_path": str(pfad), "result_filename": "screencast.mp4", **kwargs}


def test_video_kommt_zum_abspielen_und_nicht_als_download(client, video):
    with patch("src.routes.jobs._video.db.get_job", return_value=_job(video)), \
         patch("src.routes.jobs._video.USE_S3", False):
        r = client.get(f"/jobs/{UUID}/video")
    assert r.status_code == 200
    assert r.headers["content-type"] == "video/mp4"
    assert "inline" in r.headers["content-disposition"]
    assert r.headers["accept-ranges"] == "bytes"


def test_springen_liefert_nur_den_ausschnitt(client, video):
    with patch("src.routes.jobs._video.db.get_job", return_value=_job(video)), \
         patch("src.routes.jobs._video.USE_S3", False):
        r = client.get(f"/jobs/{UUID}/video", headers={"Range": "bytes=10-19"})
    assert r.status_code == 206
    assert r.content == video.read_bytes()[10:20]


def test_fremder_job_gibt_kein_video_heraus(client, video):
    with patch("src.routes.jobs._video.db.get_job", return_value=_job(video, user_id=99)):
        r = client.get(f"/jobs/{UUID}/video")
    assert r.status_code == 404


def test_unfertiger_job_hat_noch_kein_video(client, video):
    with patch("src.routes.jobs._video.db.get_job", return_value=_job(video, status="running")):
        r = client.get(f"/jobs/{UUID}/video")
    assert r.status_code == 404


def test_im_bucket_wird_der_bereich_durchgereicht(client, video):
    """Auf der Box liegt das Video im Bucket, dort muss Range mitgehen."""
    daten = video.read_bytes()[10:20]
    with patch("src.routes.jobs._video.db.get_job", return_value=_job(video)), \
         patch("src.routes.jobs._video.USE_S3", True), \
         patch("src.routes.jobs._video.stream_s3_object",
               return_value=(iter([daten]), len(daten), "bytes 10-19/2048")) as strom:
        r = client.get(f"/jobs/{UUID}/video", headers={"Range": "bytes=10-19"})
    assert strom.call_args[0][1] == "bytes=10-19"
    assert r.status_code == 206
    assert r.headers["content-range"] == "bytes 10-19/2048"
    assert r.content == daten
