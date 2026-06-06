"""Global highlight on/off switch.

Highlights (yellow span re-anchoring) are inconsistent across PDFs: precise on clean
text, broad/wrong on OCR'd documents (the keyword paragraph fallback). Until that is
robust, a single env flag turns highlights OFF for ALL modes — every chip becomes
nav-only (page/timestamp, click scrolls, no highlight). Default: OFF. The highlight
code stays in place; flip AIA_HIGHLIGHTS=1 to re-enable.
"""
from src.features.ai_assistant.routes._helpers import _highlights_enabled


def test_default_on(monkeypatch):
    monkeypatch.delenv("AIA_HIGHLIGHTS", raising=False)
    assert _highlights_enabled() is True


def test_truthy_values_enable(monkeypatch):
    for v in ("1", "true", "TRUE", "yes", "on"):
        monkeypatch.setenv("AIA_HIGHLIGHTS", v)
        assert _highlights_enabled() is True, v


def test_falsy_values_disable(monkeypatch):
    for v in ("0", "false", "no", "off", ""):
        monkeypatch.setenv("AIA_HIGHLIGHTS", v)
        assert _highlights_enabled() is False, v
