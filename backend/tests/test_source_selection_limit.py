"""Without a cap the person may hand every source of a module to a tool."""

import pytest
from fastapi import HTTPException

from src.features.ai_assistant.routes._workspace_access import _resolve_source_ids


@pytest.fixture(autouse=True)
def quellen(monkeypatch):
    """Twenty ready sources in module 1, named u1 to u20."""
    alle = {f"u{i}": {"id": i, "workspace_id": 1, "status": "ready"} for i in range(1, 21)}
    monkeypatch.setattr("src.database.get_aia_source", lambda u: alle.get(u))
    return alle


def test_twenty_sources_are_accepted():
    ids = _resolve_source_ids({"id": 1}, [f"u{i}" for i in range(1, 21)])
    assert len(ids) == 20


def test_a_cap_still_works_where_one_is_asked_for():
    with pytest.raises(HTTPException) as e:
        _resolve_source_ids({"id": 1}, ["u1", "u2", "u3"], max_count=2)
    assert e.value.status_code == 400


def test_a_source_that_is_not_ready_is_left_out():
    ids = _resolve_source_ids({"id": 1}, ["u1", "unbekannt"])
    assert ids == [1]


def test_nothing_usable_is_still_a_refusal():
    with pytest.raises(HTTPException) as e:
        _resolve_source_ids({"id": 1}, ["unbekannt"])
    assert e.value.status_code == 400
