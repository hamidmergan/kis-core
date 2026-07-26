"""Owner-export route: gates cross-student PII behind workspace ownership.

Calls the async route function directly (no app boot, no DB, no TestClient) and
monkeypatches the db facade on the route module. Depends() is bypassed when the
function is called directly, so current_user is passed as a plain dict.
"""

import asyncio

import pytest
from fastapi import HTTPException

from src.features.ai_assistant.routes import learner_profile as lp


def test_missing_workspace_is_404(monkeypatch):
    monkeypatch.setattr(lp.db, "get_aia_workspace", lambda uuid: None)

    with pytest.raises(HTTPException) as ei:
        asyncio.run(
            lp.export_enrolled_profiles("nope", current_user={"user_id": 1})
        )
    assert ei.value.status_code == 404


def test_non_owner_is_403(monkeypatch):
    """Core security check: an enrolled student or any other non-owner is refused."""
    monkeypatch.setattr(lp.db, "get_aia_workspace", lambda uuid: {"id": 1, "user_id": 999})

    with pytest.raises(HTTPException) as ei:
        asyncio.run(
            lp.export_enrolled_profiles("ws-uuid", current_user={"user_id": 1})
        )
    assert ei.value.status_code == 403


def test_owner_gets_enrolled_profiles(monkeypatch):
    weaknesses = [{
        "id": 5, "category": "term", "label": "Konjunktiv", "source_id": None,
        "effective_weight": 6.0, "hit_count": 3,
        "last_seen_at": "2026-07-26T12:00:00+00:00",
    }]
    monkeypatch.setattr(lp.db, "get_aia_workspace", lambda uuid: {"id": 1, "user_id": 1})
    monkeypatch.setattr(lp.db, "get_enrolled_user_ids", lambda wid: [2])
    monkeypatch.setattr(
        lp.db, "get_user_language_level",
        lambda uid: {"language_level": "A2", "language_level_set_at": None,
                      "language_level_skill_scores": None},
    )
    monkeypatch.setattr(lp.db, "get_learner_weaknesses", lambda uid: weaknesses)

    result = asyncio.run(
        lp.export_enrolled_profiles("ws-uuid", current_user={"user_id": 1})
    )

    assert isinstance(result, dict)
    assert result["workspace_uuid"] == "ws-uuid"
    profile = result["profiles"][0]
    assert profile["user_id"] == 2
    assert profile["level"] == "A2"
    assert profile["weaknesses"] is weaknesses
