"""The language of the scripts is recorded when they are written."""

from contextlib import contextmanager
from unittest.mock import AsyncMock, Mock

import pytest

from src.routes.screencast import _shared
from src.routes.screencast import scripts as modul
from src.routes.screencast._models import GenerateScriptsRequest


@pytest.fixture
def ablage(monkeypatch):
    gespeichert: dict[str, dict] = {}
    monkeypatch.setattr(_shared, "save_result_meta", lambda u, j, m: gespeichert.__setitem__("meta", m))
    monkeypatch.setattr(_shared, "load_result_meta", lambda u, j: {"translated_stem": "alt"})
    return gespeichert


def test_zielsprache_wird_gemerkt(ablage):
    modul._merke_skriptsprache(1, "job", "EN-US")
    assert ablage["meta"]["target_lang"] == "EN-US"
    assert ablage["meta"]["translated_stem"] == "alt"


def test_ohne_job_oder_sprache_passiert_nichts(ablage):
    modul._merke_skriptsprache(1, "job", "")
    modul._merke_skriptsprache(1, None, "EN-US")
    assert "meta" not in ablage


# --- Newly generated scripts must not leave the old audio in place ---

UUID = "d" * 32
_JOB = {"user_id": 1, "job_uuid": UUID, "status": "awaiting_user"}


@contextmanager
def _stumme_messe(*a, **k):
    yield {}


@pytest.fixture
def erzeugung_stummgeschaltet(monkeypatch):
    """Everything around the actual LLM generation is silenced, only the cache call counts."""
    monkeypatch.setattr(modul, "get_job_file", lambda u, j, name: b"[]")
    monkeypatch.setattr(modul, "save_job_file", lambda *a, **k: None)
    monkeypatch.setattr(modul, "_merke_skriptsprache", lambda *a, **k: None)
    monkeypatch.setattr(modul, "get_llm_client", lambda: object())
    monkeypatch.setattr(modul, "generate_all_scripts", AsyncMock(return_value=["a", "b"]))
    monkeypatch.setattr(modul, "messe", _stumme_messe)
    monkeypatch.setattr(modul, "route_kennung", lambda feature: {})
    monkeypatch.setattr(modul.db, "set_generating_scripts_flag", lambda *a, **k: None)


async def test_gueltiger_auftrag_wirft_die_vertonung_weg(monkeypatch, erzeugung_stummgeschaltet):
    monkeypatch.setattr(modul.db, "get_job", lambda uuid: _JOB)
    verwerfen = Mock()
    monkeypatch.setattr(modul, "vertonung_verwerfen", verwerfen)
    body = GenerateScriptsRequest(slide_texts=["a", "b"], translate_job_uuid=UUID)

    await modul.screencast_generate_scripts(body, current_user={"user_id": 1}, locale="de")

    verwerfen.assert_called_once_with(1, UUID)


async def test_ohne_auftragsnummer_bleibt_der_vorrat_unangetastet(monkeypatch, erzeugung_stummgeschaltet):
    """Scripts without a job reference have no cache to discard."""
    verwerfen = Mock()
    monkeypatch.setattr(modul, "vertonung_verwerfen", verwerfen)
    body = GenerateScriptsRequest(slide_texts=["a", "b"], translate_job_uuid=None)

    await modul.screencast_generate_scripts(body, current_user={"user_id": 1}, locale="de")

    verwerfen.assert_not_called()
