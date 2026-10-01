"""The demo delivers video, per-slide audio and presentation from prepared files."""

import base64
import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from scripts.screencast_demo_folien import abschnitte, schnitte_waehlen


@pytest.fixture
def demo_dir(tmp_path):
    (tmp_path / "accepted_scripts.json").write_text(json.dumps(["Eins", "Zwei"]), encoding="utf-8")
    (tmp_path / "output.mp4").write_bytes(b"0123456789" * 10)
    (tmp_path / "translated.pptx").write_bytes(b"PK-pptx")
    (tmp_path / "images").mkdir()
    (tmp_path / "images" / "slide-01.png").write_bytes(b"alt")
    folien = tmp_path / "folien"
    folien.mkdir()
    for i in range(2):
        (folien / f"folie_{i:03d}.png").write_bytes(f"bild{i}".encode())
        (folien / f"folie_{i:03d}.mp3").write_bytes(f"ID3ton{i}".encode())
    with patch("src.routes.screencast_demo.DEMO_DIR", tmp_path):
        yield tmp_path


@pytest.fixture
def client(demo_dir):
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


def test_bilder_kommen_aus_den_geschnittenen_folien(client):
    r = client.post("/screencast-demo/translate", json={})
    assert r.status_code == 200
    bilder = r.json()["slide_images"]
    assert [base64.b64decode(b) for b in bilder] == [b"bild0", b"bild1"]


def test_folientext_kommt_aus_der_datei(client, demo_dir):
    assert client.post("/screencast-demo/translate", json={}).json()["slide_texts"] == ["Eins", "Zwei"]
    (demo_dir / "folientexte.json").write_text(json.dumps(["Titel", "Punkte"]), encoding="utf-8")
    assert client.post("/screencast-demo/translate", json={}).json()["slide_texts"] == ["Titel", "Punkte"]


def test_ton_je_folie(client):
    r = client.get("/screencast-demo/vorschau/1")
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/mpeg"
    assert r.content == b"ID3ton1"


def test_ton_ausserhalb_der_folien_gibt_404(client):
    assert client.get("/screencast-demo/vorschau/2").status_code == 404
    assert client.get("/screencast-demo/vorschau/-1").status_code == 404


def test_video_laesst_sich_spulen(client):
    r = client.get("/screencast-demo/video", headers={"Range": "bytes=10-19"})
    assert r.status_code == 206
    assert r.content == b"0123456789"
    assert "attachment" not in r.headers.get("content-disposition", "")


def test_video_zum_herunterladen(client):
    r = client.get("/screencast-demo/video?download=true")
    assert r.status_code == 200
    assert r.headers["content-disposition"].startswith("attachment")
    assert "screencast_demo.mp4" in r.headers["content-disposition"]


def test_praesentation_zum_herunterladen(client):
    r = client.get("/screencast-demo/pptx")
    assert r.status_code == 200
    assert r.content == b"PK-pptx"
    assert "screencast_demo.pptx" in r.headers["content-disposition"]


def test_ohne_geschnittene_folien_bleiben_die_alten_bilder(client, demo_dir):
    for f in (demo_dir / "folien").iterdir():
        f.unlink()
    bilder = client.post("/screencast-demo/translate", json={}).json()["slide_images"]
    assert [base64.b64decode(b) for b in bilder] == [b"alt"]


def test_die_staerksten_schnitte_in_zeitfolge():
    kandidaten = [(5.0, 0.1), (10.0, 0.9), (2.0, 0.03), (20.0, 0.5)]
    assert schnitte_waehlen(kandidaten, 2) == [10.0, 20.0]


def test_abschnitte_decken_das_ganze_video():
    assert abschnitte([10.0, 20.0], 25.0) == [(0.0, 10.0), (10.0, 20.0), (20.0, 25.0)]
