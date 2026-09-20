# backend/tests/test_praesentation_anmeldung.py
"""Service is registered wherever a tool must be registered."""

from src import limits
from src.i18n import t
from src.permissions_registry import SYSTEM_ROLE_PERMISSIONS, TOOL_KEYS
from src.routes.admin._registries import TOOL_LABELS, TOOLS_CONFIG
from src.tools_registry import ALL_TOOL_KEYS


def test_schluessel_und_recht_existieren():
    assert "praesentation" in ALL_TOOL_KEYS
    assert "tools.praesentation" in TOOL_KEYS
    assert "tools.praesentation" in SYSTEM_ROLE_PERMISSIONS["staff"]
    assert "tools.praesentation" not in SYSTEM_ROLE_PERMISSIONS["user"]


def test_kachel_label_und_quota():
    assert any(k["key"] == "praesentation" for k in TOOLS_CONFIG)
    assert TOOL_LABELS["praesentation"] == "Präsentation"
    assert limits.QUOTA_DEFAULTS["praesentation"]["limit"] == -1
    assert (limits.PRAESENTATION_MIN_SLIDES, limits.PRAESENTATION_MAX_SLIDES) == (3, 30)


def test_meldungen_in_beiden_sprachen():
    assert t("tool.praesentation", "de") == "Präsentation"
    assert t("tool.praesentation", "en") == "Presentation"
    assert t("quota.label.praesentation", "en") == "Presentation"
    assert t("praesentation.alreadyRunning", "de") != "praesentation.alreadyRunning"


def test_quota_minus_eins_ist_unbegrenzt(monkeypatch):
    """Limit of -1 allows unlimited usage without raising an exception."""
    from src import quotas

    def _effective_limit_unlimited(*args, **kwargs):
        return -1

    monkeypatch.setattr(quotas, "_effective_limit", _effective_limit_unlimited)
    quotas.enforce_quota(7, "praesentation", False, "de")
