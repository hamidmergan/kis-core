"""Small shared helpers of the tool tasks: glossary, image route, cancel mark."""

import pytest
import redis

from src.services.feature_router import FeatureNotConfigured
from src.tasks import _cancel
from src.tasks import general_tasks as gt
from src.tasks.screencast_tasks import _shared as screencast_shared


@pytest.mark.parametrize("roh, erwartet", [
    ("", {}),
    ('{"Haus": "house"}', {"Haus": "house"}),
    ('["Haus"]', {}),
    ("kein json", {}),
])
def test_parse_glossary_only_accepts_an_object(roh, erwartet):
    assert gt.parse_glossary(roh) == erwartet


class _Client:
    closed = False

    def close(self):
        self.closed = True


def test_image_route_without_a_model_closes_its_client(monkeypatch):
    client = _Client()
    monkeypatch.setattr(gt, "_image_http_client", lambda feature, **kw: ("http://x/v1", "", client))
    with pytest.raises(FeatureNotConfigured, match="vision route has no model_name"):
        gt._image_route("vision", None, 60.0)
    assert client.closed


def test_image_route_with_a_model_hands_the_open_client_on(monkeypatch):
    client = _Client()
    monkeypatch.setattr(gt, "_image_http_client", lambda feature, **kw: ("http://x/v1", "flux", client))
    assert gt._image_route("image_gen", 3, 300.0) == ("http://x/v1", "flux", client)
    assert not client.closed


class _Redis:
    def __init__(self, marken=(), kaputt=False):
        self.marken, self.kaputt = set(marken), kaputt

    def exists(self, key):
        if self.kaputt:
            raise redis.RedisError("weg")
        return key in self.marken


def test_an_unreadable_mark_counts_as_not_cancelled_but_the_watcher_sees_the_failure(monkeypatch):
    monkeypatch.setattr(_cancel, "_r", _Redis(kaputt=True))
    assert _cancel.is_cancelled("abc") is False
    with pytest.raises(redis.RedisError):
        _cancel.mark_is_set("abc")


def test_screencast_cancel_check_kills_the_processes_of_that_job(monkeypatch):
    from src.services import screencast

    beendet = []
    monkeypatch.setattr(_cancel, "_r", _Redis({"job:cancel:abc"}))
    monkeypatch.setattr(screencast, "kill_job_procs", beendet.append)
    screencast_shared._assert_not_cancelled("other")
    with pytest.raises(screencast_shared._JobCancelled):
        screencast_shared._assert_not_cancelled("abc")
    assert beendet == ["abc"]
