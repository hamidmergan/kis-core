"""The target language has to arrive at rendering, even for an old job."""

import json

import pytest

from src.routes.screencast._models import RenderRequest


def test_render_anfrage_kennt_eine_zielsprache():
    assert RenderRequest(scripts=[], translate_job_uuid="x", provider_id=1).target_lang == ""
    body = RenderRequest(scripts=[], translate_job_uuid="x", provider_id=1, target_lang="EN-US")
    assert body.target_lang == "EN-US"


@pytest.fixture
def gespeichert(monkeypatch):
    """Captures what the route writes into the job store."""
    ablage: dict[str, dict] = {}
    from src.routes.screencast import render as modul

    monkeypatch.setattr(modul, "save_result_meta", lambda u, j, m: ablage.__setitem__("meta", m))
    monkeypatch.setattr(modul, "load_result_meta", lambda u, j: {"translated_stem": "alt"})
    return ablage, modul


def test_zielsprache_wird_fuer_die_vertonung_hinterlegt(gespeichert):
    ablage, modul = gespeichert
    modul._merke_zielsprache(1, "job", "EN-US")
    assert ablage["meta"]["target_lang"] == "EN-US"
    assert ablage["meta"]["translated_stem"] == "alt", "vorhandene Angaben bleiben stehen"


def test_ohne_zielsprache_wird_nichts_ueberschrieben(gespeichert):
    ablage, modul = gespeichert
    modul._merke_zielsprache(1, "job", "")
    assert "meta" not in ablage
