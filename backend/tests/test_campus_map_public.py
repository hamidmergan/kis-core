"""The map link of the footer is open without a session, the rest of the campus assistant is not."""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from src.features.campus.services.settings import CampusSettings

ROUTE = "src.features.campus.routes.public"


@pytest.fixture
def client_ohne_sitzung():
    from src.dependencies import get_settings
    from src.app import app

    get_settings.cache_clear()
    app.dependency_overrides.clear()
    yield TestClient(app)
    app.dependency_overrides.clear()
    get_settings.cache_clear()


def test_kartenlink_kommt_ohne_sitzung(client_ohne_sitzung):
    with patch(f"{ROUTE}.campus_settings.read", return_value=CampusSettings(map_url="https://map.test/campus-map/")):
        r = client_ohne_sitzung.get("/campus/map")
    assert r.status_code == 200
    assert r.json() == {"map_url": "https://map.test/campus-map/"}


def test_ohne_einstellung_bleibt_der_link_leer(client_ohne_sitzung):
    with patch(f"{ROUTE}.campus_settings.read", return_value=CampusSettings()):
        assert client_ohne_sitzung.get("/campus/map").json() == {"map_url": ""}
