"""The person's switch and level decide, the admin switch stays the outer gate."""

from src.features.ai_assistant.repository import language_level as ll


def _person(active: bool, level, monkeypatch, admin: bool = True):
    monkeypatch.setattr(ll, "is_language_training_enabled_globally", lambda: admin)
    monkeypatch.setattr(
        ll, "get_user_language_training",
        lambda uid: {"language_training_active": active, "language_training_asked_at": None},
    )
    monkeypatch.setattr(
        ll, "get_user_language_level",
        lambda uid: {"language_level": level, "language_level_set_at": None},
    )


def test_offered_needs_admin_and_person(monkeypatch):
    _person(True, None, monkeypatch)
    assert ll.is_language_training_offered(3) is True
    _person(False, None, monkeypatch)
    assert ll.is_language_training_offered(3) is False
    _person(True, None, monkeypatch, admin=False)
    assert ll.is_language_training_offered(3) is False


def test_ready_needs_a_level_on_top(monkeypatch):
    _person(True, None, monkeypatch)
    assert ll.is_language_training_ready(3) is False
    _person(True, "B1", monkeypatch)
    assert ll.is_language_training_ready(3) is True
    _person(False, "B1", monkeypatch)
    assert ll.is_language_training_ready(3) is False
