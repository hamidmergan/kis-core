"""The pages demo hands out one prepared page with its pictures, without jobs."""

import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


def _seite(lang: str, titel: str) -> dict:
    return {"lang": lang, "design": "chapters", "footer": "", "sections": [
        {"id": "cover", "title": "", "lead": "", "blocks": [{"kind": "image", "src": "img_0.webp", "alt": "", "prompt": "", "caption": ""}]},
        {"id": "top", "hero": True, "title": titel, "lead": "L", "meta": "", "blocks": []},
        {"id": "s1", "title": "Abschnitt", "lead": "", "blocks": [{"kind": "text", "text": "Ein Satz."}]},
        {"id": "s2", "title": "Versteckt", "lead": "", "hidden": True, "blocks": [{"kind": "text", "text": "Geheim."}]},
    ]}


@pytest.fixture
def ordner(tmp_path):
    (tmp_path / "demo.json").write_text(json.dumps({
        "workspace": "Projektmanagement", "dateien": ["A.pdf", "B.pdf"], "anweisung": "",
        "erstellt": "2026-10-09T02:18:06Z", "angaben": {"anbieter": "THL myLab"},
    }), encoding="utf-8")
    (tmp_path / "page.json").write_text(json.dumps(_seite("de", "Projektstart")), encoding="utf-8")
    (tmp_path / "page_en.json").write_text(json.dumps(_seite("en", "Project start")), encoding="utf-8")
    (tmp_path / "img_0.webp").write_bytes(b"RIFF....WEBP")
    (tmp_path / "img_7.webp").write_bytes(b"RIFF....WEBP")
    with patch("src.routes.pages_demo.DEMO_DIR", tmp_path):
        yield tmp_path


@pytest.fixture
def client(ordner):
    from src.app import app
    from src.dependencies import get_current_user
    from src.dependencies_rbac import get_user_permissions
    from src.permissions import resolve_user_permissions
    from src.security.auth import verify_auth

    app.dependency_overrides[verify_auth] = lambda: None
    app.dependency_overrides[get_current_user] = lambda: {"user_id": 1, "email": "a@b.de", "role": "staff"}
    app.dependency_overrides[get_user_permissions] = lambda: resolve_user_permissions("admin", None, True)
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_setup_names_material_and_the_one_card(client):
    daten = client.get("/pages-demo/setup").json()
    assert daten["files"] == ["A.pdf", "B.pdf"] and daten["workspace"] == "Projektmanagement"
    assert daten["card"]["title"] == "Projektstart" and daten["card"]["image"] == "img_0.webp"
    assert daten["card"]["info"] == {"anbieter": "THL myLab"}


def test_page_follows_the_language_and_hides_hidden_sections(client):
    de = client.get("/pages-demo/page", headers={"Accept-Language": "de"}).json()["page"]
    assert [s["id"] for s in de["sections"]] == ["cover", "top", "s1"]
    en = client.get("/pages-demo/page", headers={"Accept-Language": "en"}).json()["page"]
    assert en["sections"][1]["title"] == "Project start"


def test_only_pictures_the_page_shows(client):
    assert client.get("/pages-demo/images/img_0.webp").status_code == 200
    assert client.get("/pages-demo/images/img_7.webp").status_code == 404
    assert client.get("/pages-demo/images/demo.json").status_code == 404


def test_without_a_prepared_page_there_is_no_card(client, ordner):
    (ordner / "page.json").unlink()
    (ordner / "page_en.json").unlink()
    assert client.get("/pages-demo/setup").json()["card"] is None
    assert client.get("/pages-demo/page").status_code == 404
