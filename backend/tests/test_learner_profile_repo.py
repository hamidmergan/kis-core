"""Offline test for the admin window parsing. DB paths are verified in the app."""
from src.features.ai_assistant.repository import learner_profile as repo


def test_window_days_falls_back_on_bad_value(monkeypatch):
    monkeypatch.setattr(repo, "get_setting", lambda *a, **k: "not-a-number")
    assert repo._window_days() == 30


def test_window_days_reads_setting(monkeypatch):
    monkeypatch.setattr(repo, "get_setting", lambda *a, **k: "90")
    assert repo._window_days() == 90


def test_window_days_never_below_one(monkeypatch):
    monkeypatch.setattr(repo, "get_setting", lambda *a, **k: "0")
    assert repo._window_days() == 1
