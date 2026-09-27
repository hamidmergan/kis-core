"""An enrollment link may be created and shown without an expiry date."""

import asyncio
from datetime import datetime

import pytest
from fastapi import HTTPException

from src.features.ai_assistant.routes import workspaces as routes

WORKSPACE = {"id": 7, "uuid": "w-1", "user_id": 1}


# --- creating without a date ----------------------------------------------

def test_leeres_datum_heisst_unbegrenzt():
    assert routes._parse_optional_expiry(None, "de") is None
    assert routes._parse_optional_expiry("", "de") is None


def test_datum_wird_als_utc_gelesen():
    ergebnis = routes._parse_optional_expiry("2027-01-01T00:00:00", "de")
    assert ergebnis == datetime(2027, 1, 1, 0, 0, 0, tzinfo=ergebnis.tzinfo)
    assert ergebnis.utcoffset().total_seconds() == 0


def test_unsinniges_datum_bleibt_ein_fehler():
    """Optional does not mean garbage silently becomes 'unlimited'."""
    with pytest.raises(HTTPException) as fehler:
        routes._parse_optional_expiry("kein datum", "de")
    assert fehler.value.status_code == 400


@pytest.fixture
def links(monkeypatch):
    """Stubs out the access check and the database and returns the given links."""
    def einrichten(rows):
        monkeypatch.setattr(routes, "_require_workspace_manage", lambda *a, **k: WORKSPACE)
        monkeypatch.setattr(routes.db, "get_access_links_by_workspace", lambda ws_id: rows)
    return einrichten


def _aufrufen():
    return (routes.list_access_links("w-1", {"user_id": 1}, "de"))


def test_link_ohne_ablaufdatum(links):
    links([{"id": 1, "code": "abc12345", "expires_at": None, "created_at": None}])
    ergebnis = _aufrufen()
    assert ergebnis == [
        {"id": 1, "code": "abc12345", "expires_at": None, "created_at": None}
    ]


def test_link_mit_ablaufdatum_bleibt_unveraendert(links):
    wann = datetime(2027, 1, 1, 12, 0, 0)
    links([{"id": 2, "code": "def67890", "expires_at": wann, "created_at": wann}])
    ergebnis = _aufrufen()
    assert ergebnis[0]["expires_at"] == "2027-01-01T12:00:00Z"
    assert ergebnis[0]["created_at"] == "2027-01-01T12:00:00Z"


def test_gemischte_liste(links):
    """A single link without a deadline must not break the whole list."""
    links([
        {"id": 1, "code": "aaa11111", "expires_at": None, "created_at": None},
        {"id": 2, "code": "bbb22222", "expires_at": datetime(2027, 1, 1), "created_at": None},
    ])
    ergebnis = _aufrufen()
    assert [e["code"] for e in ergebnis] == ["aaa11111", "bbb22222"]
    assert ergebnis[0]["expires_at"] is None
    assert ergebnis[1]["expires_at"] == "2027-01-01T00:00:00Z"
