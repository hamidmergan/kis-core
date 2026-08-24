"""Die Sprache der Skripte wird schon beim Schreiben gemerkt.

Sonst haengt die Vertonung daran, dass der Browser sie spaeter mitschickt.
Die Skripte werden immer in einer Zielsprache geschrieben, auch wenn die
Uebersetzung uebersprungen wurde.
"""

import pytest

from src.routes.screencast import scripts as modul


@pytest.fixture
def ablage(monkeypatch):
    gespeichert: dict[str, dict] = {}
    monkeypatch.setattr(modul, "save_result_meta", lambda u, j, m: gespeichert.__setitem__("meta", m))
    monkeypatch.setattr(modul, "load_result_meta", lambda u, j: {"translated_stem": "alt"})
    return gespeichert


def test_zielsprache_wird_gemerkt(ablage):
    modul._merke_skriptsprache(1, "job", "EN-US")
    assert ablage["meta"]["target_lang"] == "EN-US"
    assert ablage["meta"]["translated_stem"] == "alt"


def test_ohne_job_oder_sprache_passiert_nichts(ablage):
    modul._merke_skriptsprache(1, "job", "")
    modul._merke_skriptsprache(1, None, "EN-US")
    assert "meta" not in ablage
