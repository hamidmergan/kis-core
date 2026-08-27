"""The screencast_translate route is gone, the job type stays."""

from src.features.ai_providers.repository.feature_routes import (
    FEATURES,
    USER_CHOICE_FEATURES,
)
from src.services.feature_route_check import _CHAT_LIKE_FEATURES


def test_route_is_gone():
    assert "screencast_translate" not in FEATURES
    assert "screencast_translate" not in USER_CHOICE_FEATURES
    assert "screencast_translate" not in _CHAT_LIKE_FEATURES


def test_doc_translate_still_exists_and_stays_user_choice():
    """It is the replacement, without it nobody can translate any more."""
    assert "doc_translate" in FEATURES
    assert "doc_translate" in USER_CHOICE_FEATURES


def test_job_tool_name_is_untouched():
    """The job type keeps its name, otherwise old jobs disappear."""
    from src.routes.admin._registries import TOOL_LABELS

    assert "screencast_translate" in TOOL_LABELS
