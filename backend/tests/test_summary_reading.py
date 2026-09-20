"""Eine Datei, ein Aufruf: Fakten mit Beleg, nach festem Schema, mit Rueckfall."""

import asyncio
import json

import pytest

from tests.summary_helpers import FakeClient

from src.features.summary import reading as rd
from src.features.summary.models import Caller
from src.limits import SUMMARY_READ_MAX_ATTEMPTS
from src.services.model_limits import CHARS_PER_TOKEN

_QUELLE = {"source_id": "doc_01", "filename": "a.pdf", "content": "Stoff"}
_KATEGORIEN = ("deadline", "figure")


def _caller(antworten):
    return Caller(FakeClient(antworten), "m")


def _antwort(*aussagen: str) -> str:
    return json.dumps({"facts": [
        {"category": "deadline", "fact": a, "citation": f"Beleg {a}"} for a in aussagen
    ]})


class _Abgewiesen(Exception):
    def __init__(self, status: int, text: str = "zu viel"):
        super().__init__(text)
        self.status_code = status


class _Zeitueberschreitung(Exception):
    pass


_Zeitueberschreitung.__name__ = "APITimeoutError"


async def _sofort(*_args, **_kwargs):
    """Wartezeiten wegnehmen, ohne die echte Schlaffunktion erneut aufzurufen."""
    return None


async def _lies(caller, **kwargs):
    return await rd.read_source(caller, source=_QUELLE, language="German",
                                template_body="BAUPLAN XY", categories=_KATEGORIEN,
                                **{"max_chars": 6_000, "max_facts": 40, **kwargs})


@pytest.fixture(autouse=True)
def _schema_modus_zuruecksetzen():
    rd._schema_mode_supported = True
    yield
    rd._schema_mode_supported = True


async def test_der_auftrag_traegt_vorlage_sprache_und_suchraster():
    caller = _caller([_antwort("A")])
    await _lies(caller)
    system = caller.client.system_prompts()[0]
    assert "BAUPLAN XY" in system
    assert "Write in German." in system
    assert "- deadline" in system and "- figure" in system
    assert "strict extractor" in system


async def test_die_ganze_datei_geht_in_einen_aufruf():
    caller = _caller([_antwort("A")])
    await _lies(caller)
    assert len(caller.client.gesendet) == 1
    assert "Stoff" in caller.client.user_prompts()[0]


async def test_das_feste_schema_wird_mitgeschickt():
    caller = _caller([_antwort("A")])
    await _lies(caller)
    assert caller.client.optionen[0]["response_format"] is rd.FACTS_SCHEMA


async def test_die_ausgabe_reicht_fuer_die_verlangten_fakten():
    """Der Deckel folgt der Zahl der Fakten, sonst schneidet er jede lange Antwort ab."""
    caller = _caller([_antwort("A")])
    await _lies(caller, max_chars=9_000)
    fakten = 9_000 // rd.CHARS_PER_FACT
    assert caller.client.optionen[0]["max_tokens"] == \
        int(fakten * rd._ANSWER_CHARS_PER_FACT / CHARS_PER_TOKEN)


async def test_der_ausgabedeckel_aus_dem_adminbereich_gewinnt(monkeypatch):
    """Ein von Hand hochgesetzter Faktendeckel darf die Antwort nicht ins Unendliche treiben."""
    monkeypatch.setattr(rd.cfg, "output_tokens_cap", lambda: 4_000)
    caller = _caller([_antwort("A")])

    await _lies(caller, max_chars=30_000, max_facts=80)

    assert caller.client.optionen[0]["max_tokens"] == 4_000


async def test_fakten_kommen_mit_kategorie_und_beleg_zurueck():
    caller = _caller([_antwort("A")])
    fakten = await _lies(caller)
    assert fakten == [{"category": "deadline", "fact": "A", "citation": "Beleg A",
                       "reference": ""}]


async def test_mehr_fakten_als_erlaubt_werden_abgeschnitten():
    caller = _caller([_antwort(*[f"A{i}" for i in range(50)])])
    fakten = await _lies(caller, max_chars=1_500)
    assert len(fakten) == 5


async def test_ein_anbieter_ohne_schema_modus_wird_ohne_gefragt():
    """Ohne diesen Rueckfall verliert der Dienst bei so einem Anbieter jede Datei."""
    caller = _caller([_Abgewiesen(400, "response_format not supported"), _antwort("A")])
    fakten = await _lies(caller)
    assert fakten[0]["fact"] == "A"
    assert "response_format" not in caller.client.optionen[1]
    assert rd._schema_mode_supported is False


async def test_eine_absage_wegen_andrang_reicht_die_bremse_nach_oben():
    for fehler in (_Abgewiesen(429), _Abgewiesen(503), _Zeitueberschreitung()):
        caller = _caller([fehler])
        with pytest.raises(rd.RateLimited):
            await _lies(caller)
        assert len(caller.client.gesendet) == 1


async def test_ein_anderer_fehler_wird_wiederholt_und_dann_ausgelassen(monkeypatch):
    monkeypatch.setattr(rd.asyncio, "sleep", _sofort)
    caller = _caller([RuntimeError("kaputt")] * SUMMARY_READ_MAX_ATTEMPTS)
    assert await _lies(caller) is None
    assert len(caller.client.gesendet) == SUMMARY_READ_MAX_ATTEMPTS


async def test_eine_leere_antwort_gilt_als_fehlschlag(monkeypatch):
    monkeypatch.setattr(rd.asyncio, "sleep", _sofort)
    caller = _caller(['{"facts": []}'] * SUMMARY_READ_MAX_ATTEMPTS)
    assert await _lies(caller) is None


def test_andrang_wird_an_status_und_namen_erkannt():
    assert rd.overloaded(_Abgewiesen(429))
    assert rd.overloaded(_Abgewiesen(503))
    assert rd.overloaded(_Zeitueberschreitung())
    assert rd.overloaded(asyncio.TimeoutError())
    assert not rd.overloaded(_Abgewiesen(400))
    assert not rd.overloaded(RuntimeError("kaputt"))
