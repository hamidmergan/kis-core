"""The permission and the level decide, the admin switch stays the outer gate."""

from src.features.ai_assistant.repository import language_level as ll


class _FakeCursor:
    def __init__(self, calls):
        self._calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        # Untruncated, otherwise the test would silently pass.
        self._calls.append((" ".join(sql.split()), params))


class _FakeConn:
    def __init__(self, calls):
        self._calls = calls

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def cursor(self, **kwargs):
        return _FakeCursor(self._calls)

    def commit(self):
        pass


def _person(allowed: bool, level, monkeypatch, admin: bool = True, active: bool = True):
    monkeypatch.setattr(ll, "is_language_training_enabled_globally", lambda: admin)
    monkeypatch.setattr(ll, "may_use_language_training", lambda uid: allowed)
    monkeypatch.setattr(
        ll, "get_user_language_level",
        lambda uid: {"language_level": level, "language_level_set_at": None},
    )
    monkeypatch.setattr(
        ll, "get_user_language_training",
        lambda uid: {"language_training_active": active, "language_training_asked_at": None},
    )


def test_offered_needs_admin_and_permission(monkeypatch):
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


def test_ready_needs_the_person_switch(monkeypatch):
    """Switched off means no tiles and no level adaptation, the page stays open."""
    _person(True, "B1", monkeypatch, active=False)
    assert ll.is_language_training_ready(3) is False
    assert ll.is_language_training_offered(3) is True


def test_set_user_language_training_keeps_the_first_asked_at(monkeypatch):
    """The start question must not be asked again once it was answered once."""
    calls: list[tuple] = []
    monkeypatch.setattr(ll, "get_connection", lambda: _FakeConn(calls))

    ll.set_user_language_training(3, False)

    sql, params = calls[0]
    assert "COALESCE(language_training_asked_at, NOW())" in sql
    assert params == (False, 3)


def test_first_level_switches_on_a_later_one_does_not(monkeypatch):
    """A deliberate off must survive a level change."""
    monkeypatch.setattr(ll, "get_connection", lambda: _FakeConn([]))
    switched: list[bool] = []
    monkeypatch.setattr(ll, "set_user_language_training", lambda uid, active: switched.append(active))

    monkeypatch.setattr(
        ll, "get_user_language_training",
        lambda uid: {"language_training_active": False, "language_training_asked_at": None},
    )
    ll.set_user_language_level(3, "B1", "self")
    assert switched == [True]

    monkeypatch.setattr(
        ll, "get_user_language_training",
        lambda uid: {"language_training_active": False, "language_training_asked_at": "2026-09-04"},
    )
    ll.set_user_language_level(3, "B2", "self")
    assert switched == [True]
