"""The mode without a login hangs on its own switch now."""

import pytest

from src.config import Settings


def test_the_switch_turns_the_mode_on():
    assert Settings(auth_disabled=True).is_local_mode is True


def test_it_is_off_by_default():
    assert Settings().is_local_mode is False


def test_production_together_with_the_switch_refuses_to_start(monkeypatch):
    monkeypatch.setenv("PRODUCTION", "true")
    monkeypatch.setenv("AUTH_DISABLED", "true")
    from fastapi.testclient import TestClient

    from src.app import create_app
    from src.dependencies import get_settings

    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError, match="AUTH_DISABLED"):
            with TestClient(create_app()):
                pass
    finally:
        get_settings.cache_clear()
