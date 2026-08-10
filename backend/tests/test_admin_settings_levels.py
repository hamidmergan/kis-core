"""Admin-API für die Stufen-Beschreibungen: lesen, speichern, zurücksetzen.

Der direkte Aufruf von ``update_settings`` reicht hier: die Depends-Argumente sind
gewöhnliche Vorgabewerte, und ``settings.py`` importiert ``db`` auf Modulebene,
also greift der monkeypatch. Einen Testclient gibt es in dieser Testsuite nicht.
"""

import json

import pytest
from fastapi import HTTPException

from src.routes.admin import settings as admin_settings
from src.services.aia_level_ladder import (
    DEFAULT_LEVEL_DESCRIPTIONS,
    LEVEL_DESCRIPTIONS_SETTING,
)


class _Body:
    """Minimaler Ersatz für UpdateSettingsRequest: alles None ausser einem Feld."""

    def __init__(self, **kwargs):
        object.__setattr__(self, "_set", kwargs)

    def __getattr__(self, name):
        return object.__getattribute__(self, "_set").get(name)


@pytest.fixture
def store(monkeypatch):
    data = {}
    monkeypatch.setattr(
        admin_settings.db, "get_setting", lambda key, default="": data.get(key, default)
    )
    monkeypatch.setattr(
        admin_settings.db, "set_setting", lambda key, value: data.__setitem__(key, value)
    )
    return data


async def test_patch_stores_valid_json(store):
    payload = json.dumps({"B1": "Meine B1-Beschreibung."})
    await admin_settings.update_settings(
        _Body(language_diagnosis_level_descriptions=payload), None, "de"
    )
    assert store[LEVEL_DESCRIPTIONS_SETTING] == payload


async def test_patch_empty_resets(store):
    store[LEVEL_DESCRIPTIONS_SETTING] = '{"B1": "alt"}'
    await admin_settings.update_settings(
        _Body(language_diagnosis_level_descriptions="  "), None, "de"
    )
    assert store[LEVEL_DESCRIPTIONS_SETTING] == ""


async def test_patch_rejects_broken_json(store):
    with pytest.raises(HTTPException) as exc:
        await admin_settings.update_settings(
            _Body(language_diagnosis_level_descriptions="{kaputt"), None, "de"
        )
    assert exc.value.status_code == 400


async def test_patch_rejects_unknown_level(store):
    with pytest.raises(HTTPException) as exc:
        await admin_settings.update_settings(
            _Body(language_diagnosis_level_descriptions=json.dumps({"D1": "nein"})),
            None,
            "de",
        )
    assert exc.value.status_code == 400


def test_defaults_are_offered_to_the_card():
    assert set(DEFAULT_LEVEL_DESCRIPTIONS) == {"A1", "A2", "B1", "B2", "C1", "C2"}
