"""Checks the global text recognition switch."""
from src.services import aia_ocr
from src.services import feature_router


def test_ocr_disabled_globally_returns_none(monkeypatch):
    # Switch off means no provider, the route is not even read.
    monkeypatch.setattr("src.database.get_setting", lambda key, default="": "false")

    def explode(_feature):  # pragma: no cover - must not be reached
        raise AssertionError("resolve() should not be called when OCR is off")

    monkeypatch.setattr(feature_router, "resolve", explode)
    assert aia_ocr.get_ocr_provider() is None


def test_ocr_enabled_by_default_consults_route(monkeypatch):
    # Setting absent → defaults to enabled → resolver path runs for feature "ocr".
    monkeypatch.setattr("src.database.get_setting", lambda key, default="": default)
    seen = {}

    def fake_resolve(feature):
        seen["feature"] = feature
        raise feature_router.FeatureNotConfigured("no route")

    monkeypatch.setattr(feature_router, "resolve", fake_resolve)
    assert aia_ocr.get_ocr_provider() is None
    assert seen["feature"] == "ocr"
