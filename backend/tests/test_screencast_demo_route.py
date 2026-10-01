"""The demo delivers slides, videos per voice service and audio from prepared files."""

import base64
import io
import json
import zipfile
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

STIMMEN = [
    {"id": "hpc", "anbieter": "HPC", "eigen": True,
     "sprachen": {"de": {"name": "Thorsten", "stimme": "thorsten"}, "en": {"name": "Michael", "stimme": "am_michael"}}},
    {"id": "gemini", "anbieter": "Gemini", "eigen": False,
     "sprachen": {"de": {"name": "Charon"}, "en": {"name": "Charon"}}},
]


def _sprache(wurzel, sprache: str, videos: list[str]):
    ordner = wurzel / sprache
    (ordner / "folien").mkdir(parents=True)
    (ordner / "accepted_scripts.json").write_text(json.dumps([f"Eins {sprache}", f"Zwei {sprache}"]), encoding="utf-8")
    (ordner / "folientexte.json").write_text(json.dumps([f"Titel {sprache}", f"Punkte {sprache}"]), encoding="utf-8")
    (ordner / "Projektstart.pptx").write_bytes(f"PK-{sprache}".encode())
    for i in range(2):
        (ordner / "folien" / f"folie_{i:03d}.png").write_bytes(f"bild{i}{sprache}".encode())
    for kennung in videos:
        (ordner / "videos").mkdir(exist_ok=True)
        (ordner / "videos" / f"{kennung}.mp4").write_bytes(f"{kennung}{sprache}-".encode() + b"0123456789" * 10)
        ton = ordner / "ton" / kennung
        ton.mkdir(parents=True)
        for i in range(2):
            (ton / f"folie_{i:03d}.mp3").write_bytes(f"ID3{kennung}{i}".encode())


@pytest.fixture
def demo_dir(tmp_path):
    (tmp_path / "stimmen.json").write_text(json.dumps(STIMMEN), encoding="utf-8")
    _sprache(tmp_path, "de", ["hpc", "gemini"])
    _sprache(tmp_path, "en", ["hpc"])
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


def test_folien_und_texte_je_sprache(client):
    de = client.post("/screencast-demo/translate", json={}).json()
    en = client.post("/screencast-demo/translate?sprache=en", json={}).json()
    assert [base64.b64decode(b) for b in de["slide_images"]] == [b"bild0de", b"bild1de"]
    assert de["slide_texts"] == ["Titel de", "Punkte de"]
    assert en["slide_texts"] == ["Titel en", "Punkte en"]


def test_skripte_je_sprache(client):
    assert client.post("/screencast-demo/generate-scripts?sprache=en").json()["scripts"] == ["Eins en", "Zwei en"]


def test_unbekannte_sprache_nimmt_die_standardsprache(client):
    assert client.post("/screencast-demo/translate?sprache=fr", json={}).json()["slide_texts"] == ["Titel de", "Punkte de"]
    assert client.post("/screencast-demo/translate?sprache=../en", json={}).json()["slide_texts"] == ["Titel de", "Punkte de"]


def test_stimmen_in_ihrer_reihenfolge_mit_vorhandenen_videos(client):
    stimmen = client.get("/screencast-demo/stimmen").json()["stimmen"]
    assert [s["id"] for s in stimmen] == ["hpc", "gemini"]
    assert stimmen[0] == {"id": "hpc", "anbieter": "HPC", "eigen": True,
                          "stimmen": {"de": "Thorsten", "en": "Michael"},
                          "kennungen": {"de": "thorsten", "en": "am_michael"}, "videos": ["de", "en"]}
    assert stimmen[1]["videos"] == ["de"]


def test_video_je_anbieter(client):
    assert client.get("/screencast-demo/video?anbieter=gemini").content.startswith(b"geminide-")
    assert client.get("/screencast-demo/video?sprache=en&anbieter=hpc").content.startswith(b"hpcen-")


def test_fehlendes_video_nimmt_den_ersten_anbieter(client):
    assert client.get("/screencast-demo/video?sprache=en&anbieter=gemini").content.startswith(b"hpcen-")
    assert client.get("/screencast-demo/video?anbieter=../x").content.startswith(b"hpcde-")


def test_video_laesst_sich_spulen(client):
    r = client.get("/screencast-demo/video?anbieter=hpc", headers={"Range": "bytes=6-15"})
    assert r.status_code == 206
    assert r.content == b"0123456789"
    assert "attachment" not in r.headers.get("content-disposition", "")


def test_video_zum_herunterladen(client):
    r = client.get("/screencast-demo/video?anbieter=gemini&download=true")
    assert r.status_code == 200
    assert r.headers["content-disposition"].startswith("attachment")
    assert "screencast_demo_gemini.mp4" in r.headers["content-disposition"]


def test_ton_je_folie_vom_ersten_anbieter(client):
    r = client.get("/screencast-demo/vorschau/1?sprache=en")
    assert r.status_code == 200
    assert r.headers["content-type"] == "audio/mpeg"
    assert r.content == b"ID3hpc1"


def test_ton_ausserhalb_der_folien_gibt_404(client):
    assert client.get("/screencast-demo/vorschau/2").status_code == 404
    assert client.get("/screencast-demo/vorschau/-1").status_code == 404


def test_praesentation_je_sprache(client):
    r = client.get("/screencast-demo/pptx?sprache=en")
    assert r.status_code == 200
    assert r.content == b"PK-en"
    assert "Projektstart.pptx" in r.headers["content-disposition"]


def test_buendel_mit_dem_video_des_anbieters(client):
    r = client.get("/screencast-demo/bundle?anbieter=gemini")
    assert r.status_code == 200
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        assert set(zf.namelist()) >= {"screencast.mp4", "accepted_scripts.json", "Projektstart.pptx"}
        assert zf.read("screencast.mp4").startswith(b"geminide-")


def test_ohne_daten_meldet_die_demo_nichts_verfuegbar(client, demo_dir):
    with patch("src.routes.screencast_demo.DEMO_DIR", demo_dir / "fehlt"):
        assert client.get("/screencast-demo/available").json()["available"] is False
        assert client.get("/screencast-demo/stimmen").json()["stimmen"] == []
