"""Jedes erzeugte Bild braucht einen Platz beim Anbieter, sonst stauen sich die Bilder dort.

Lasttest 26.09.: myLab malt genau ein Bild zur Zeit, etwa 11 s je Bild. Bis zu 24 Bilder
gleichzeitig liefen in die 300 s Grenze, 92 von rund 110 Präsentationsbildern fehlten.
"""

import base64
import contextlib

import pytest

from src.features.praesentation import bild
from src.limits import IMAGE_PROVIDER_MAX_CONCURRENT
from src.services.provider_slots import ProviderFull
from src.services.upstream_errors import is_upstream_busy
from src.tasks import general_tasks as gt


class _Antwort:
    status_code = 200
    text = ""

    def json(self):
        return {"data": [{"b64_json": base64.b64encode(b"png").decode()}]}


class _Client:
    def __init__(self, protokoll):
        self.protokoll = protokoll

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def post(self, url, json=None, **_):
        self.protokoll.append("post")
        return _Antwort()


@pytest.fixture
def protokoll(monkeypatch):
    eintraege = []
    monkeypatch.setattr(bild, "_image_http_client",
                        lambda feature, **kw: ("https://models.mylab.example/v1", "flux", _Client(eintraege)))
    return eintraege


def _platz(protokoll):
    @contextlib.contextmanager
    def platz(provider, *, limit, wait_seconds):
        protokoll.append(("platz", provider, limit))
        yield
        protokoll.append("frei")
    return platz


def _voll(provider, *, limit, wait_seconds):
    raise ProviderFull(provider, wait_seconds)


def test_ein_praesentationsbild_malt_nur_mit_platz(monkeypatch, protokoll):
    monkeypatch.setattr(gt.provider_slots, "slot", _platz(protokoll))

    assert bild.erzeuge("a lab", "1024x576") == b"png"
    assert protokoll == [("platz", "models.mylab.example/images", IMAGE_PROVIDER_MAX_CONCURRENT), "post", "frei"]


def test_ohne_platz_geht_keine_anfrage_raus(monkeypatch, protokoll):
    monkeypatch.setattr(gt.provider_slots, "slot", _voll)

    with pytest.raises(ProviderFull):
        bild.erzeuge("a lab", "1024x576")
    assert protokoll == []


def test_der_bildauftrag_wartet_auf_denselben_platz(monkeypatch):
    protokoll, gemeldet = [], []
    monkeypatch.setattr(gt.db, "update_job_status", lambda *a, **k: None)
    monkeypatch.setattr(gt, "_resolve_user_id", lambda j: 1)
    monkeypatch.setattr(gt, "_image_http_client",
                        lambda *a, **k: ("https://models.mylab.example/v1", "flux", _Client(protokoll)))
    monkeypatch.setattr(gt.provider_slots, "slot", _voll)
    monkeypatch.setattr(gt, "_handle_task_exception", lambda job, e, task_label: gemeldet.append(e))

    with pytest.raises(ProviderFull):
        gt.run_image_generate.run.__func__(None, "job1", "a cat", "1024x1024", None)
    assert protokoll == []
    # The busy wording makes the job wait instead of burning an attempt.
    assert isinstance(gemeldet[0], ProviderFull) and is_upstream_busy(gemeldet[0])
