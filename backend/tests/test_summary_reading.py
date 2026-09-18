"""Reading one unit: the build plan steers what is taken first, the cap what is returned."""

import pytest

from tests.summary_helpers import FakeClient

from src.features.summary import reading as rd
from src.features.summary.models import Caller
from src.limits import SUMMARY_READ_MAX_ATTEMPTS
from src.services.model_limits import CHARS_PER_TOKEN

_EINHEIT = {"source_id": "q1", "filename": "a.pdf", "content": "Stoff", "part": 1, "parts": 1}


def _caller(antworten):
    return Caller(FakeClient(antworten), "m")


async def test_der_auftrag_traegt_die_vorlage_und_die_wortzahl():
    caller = _caller(["- Fakt"])
    await rd.read_unit(caller, unit=_EINHEIT, language="German",
                       template_body="BAUPLAN XY", max_chars=7_000)
    system = caller.client.system_prompts()[0]
    assert "BAUPLAN XY" in system
    assert "Stay under 1000 words" in system
    assert "Write in German." in system


async def test_die_ausgabe_ist_hart_gedeckelt():
    caller = _caller(["- Fakt"])
    await rd.read_unit(caller, unit=_EINHEIT, language="German",
                       template_body="B", max_chars=9_000)
    assert caller.client.optionen[0]["max_tokens"] == int(9_000 / CHARS_PER_TOKEN)


async def test_ein_ausschnitt_wird_als_solcher_angesprochen():
    caller = _caller(["- Fakt"])
    teil = dict(_EINHEIT, source_id="q1t2", part=2, parts=3)
    await rd.read_unit(caller, unit=teil, language="German", template_body="B", max_chars=5_000)
    assert "excerpt 2 of 3" in caller.client.system_prompts()[0]
    assert "excerpt 2 of 3" in caller.client.user_prompts()[0]


async def test_ein_ganzes_dokument_kennt_keinen_ausschnitt():
    caller = _caller(["- Fakt"])
    await rd.read_unit(caller, unit=_EINHEIT, language="German", template_body="B", max_chars=5_000)
    assert "excerpt" not in caller.client.system_prompts()[0]


async def test_eine_abgeschnittene_antwort_verliert_nur_die_halbe_zeile():
    caller = _caller([("- eins\n- zwei\n- dr", "length")])
    text = await rd.read_unit(caller, unit=_EINHEIT, language="German",
                              template_body="B", max_chars=5_000)
    assert text == "- eins\n- zwei"


def test_zuschneiden_behaelt_einen_kurzen_text_ganz():
    assert rd.cut_to_last_line("- eins\n- zw") == "- eins"
    assert rd.cut_to_last_line("- z\n- eins zwei drei vier") == "- z\n- eins zwei drei vier"
    assert rd.cut_to_last_line("kein Umbruch") == "kein Umbruch"


async def test_nach_allen_versuchen_kommt_none(monkeypatch):
    monkeypatch.setattr(rd, "SUMMARY_RETRY_DELAY_SECONDS", 0)
    caller = _caller([RuntimeError("kaputt")] * SUMMARY_READ_MAX_ATTEMPTS)
    assert await rd.read_unit(caller, unit=_EINHEIT, language="German",
                              template_body="B", max_chars=5_000) is None
    assert len(caller.client.gesendet) == SUMMARY_READ_MAX_ATTEMPTS


async def test_ein_zweiter_versuch_rettet_die_einheit(monkeypatch):
    monkeypatch.setattr(rd, "SUMMARY_RETRY_DELAY_SECONDS", 0)
    caller = _caller([RuntimeError("kurz weg"), "- Fakt"])
    assert await rd.read_unit(caller, unit=_EINHEIT, language="German",
                              template_body="B", max_chars=5_000) == "- Fakt"
