"""One run end to end, with the store in memory and the model faked."""

import asyncio
import json

import pytest

from tests.summary_helpers import FakeClient, MemoryStore

from src.features.summary import pipeline as pl
from src.features.summary import reading as rd
from src.features.summary.models import Caller
from src.features.summary.templates import get_template
from src.limits import SUMMARY_FACTS_MAX_CHARS, SUMMARY_FACTS_MIN_CHARS
from src.services.model_limits import CHARS_PER_TOKEN

_PLAN = json.dumps({"intro": "Vorweg.", "sections": [
    {"title": "A", "scope": "a"}, {"title": "B", "scope": "b"}, {"title": "C", "scope": "c"}]})
_VORLAGE = get_template("kurzbriefing")


def _einheit(nr, **extra):
    return {"source_id": f"q{nr}", "filename": f"{nr}.pdf", "content": "X" * 50,
            "origin": f"q{nr}", "part": 1, "parts": 1, "label": f"{nr}.pdf", **extra}


def _caller(antworten):
    return Caller(FakeClient(antworten), "m")


@pytest.fixture(autouse=True)
def _kein_budget_aus_der_datenbank(monkeypatch):
    monkeypatch.setattr(pl, "facts_budget", lambda: 440_000)
    monkeypatch.setattr(pl, "SUMMARY_MAP_CONCURRENCY", 1)
    monkeypatch.setattr(rd, "SUMMARY_RETRY_DELAY_SECONDS", 0)


class TestFaktenAnteil:
    def test_eine_einheit_bekommt_den_hoechstwert(self):
        assert pl.facts_per_unit(1) == SUMMARY_FACTS_MAX_CHARS

    def test_viele_einheiten_teilen_sich_das_budget(self):
        assert pl.facts_per_unit(100) == 4_400

    def test_unter_den_mindestwert_geht_es_nie(self):
        assert pl.facts_per_unit(1000) == SUMMARY_FACTS_MIN_CHARS


class TestSprache:
    def test_die_probe_kommt_aus_der_mitte(self):
        text = "A" * 5000 + "MITTE" + "B" * 5000
        assert "MITTE" in pl.language_sample(text, 400)

    def test_eine_geschwaetzige_antwort_wird_verworfen(self):
        assert pl.clean_language_name("The language is German.") is None
        assert pl.clean_language_name("German") == "German"


class TestEinLauf:
    async def test_ein_ganzer_lauf_in_reihenfolge(self):
        store = MemoryStore()
        caller = _caller(["German", "- A", "- B", _PLAN, "Text A", "Text B", "Text C"])

        text = await pl.run_pipeline(caller, units=[_einheit(1), _einheit(2)],
                                     template=_VORLAGE, store=store)

        assert text.startswith("Vorweg.") and "## A\n\nText A" in text and "## C" in text
        assert store.language == "German"
        assert store.extractions == {"q1": "- A", "q2": "- B"}
        assert store.outline["intro"] == "Vorweg."
        assert store.sections == {0: "Text A", 1: "Text B", 2: "Text C"}
        assert ("outline", None, None) in store.schritte
        assert ("section", 3, 3) in store.schritte

    async def test_jede_einheit_bekommt_ihren_anteil_und_die_vorlage(self, monkeypatch):
        monkeypatch.setattr(pl, "facts_budget", lambda: 24_000)
        caller = _caller(["German", "- A", "- B", "- C", _PLAN, "Text A", "Text B", "Text C"])
        await pl.run_pipeline(caller, units=[_einheit(1), _einheit(2), _einheit(3)],
                              template=_VORLAGE, store=MemoryStore())
        erwartet = int(8_000 / CHARS_PER_TOKEN)
        assert [o.get("max_tokens") for o in caller.client.optionen[1:4]] == [erwartet] * 3
        assert "briefing" in caller.client.system_prompts()[1].lower()

    async def test_der_planer_erfaehrt_welche_teile_zusammengehoeren(self):
        teile = [_einheit(1, source_id="q1t1", part=1, parts=2, label="1.pdf (Teil 1 von 2)"),
                 _einheit(1, source_id="q1t2", part=2, parts=2, label="1.pdf (Teil 2 von 2)")]
        caller = _caller(["German", "- A", "- B", _PLAN, "Text A", "Text B", "Text C"])
        await pl.run_pipeline(caller, units=teile, template=_VORLAGE, store=MemoryStore())
        assert "- 1.pdf: q1t1, q1t2" in caller.client.system_prompts()[3]

    async def test_eine_unlesbare_gliederung_faellt_auf_den_einzelaufruf_zurueck(self, monkeypatch):
        from src.features.summary import writing as wr
        monkeypatch.setattr(wr, "SUMMARY_RETRY_DELAY_SECONDS", 0)
        store = MemoryStore()
        caller = _caller(["German", "- A", "nix", "nix", "Der ganze Text."])
        text = await pl.run_pipeline(caller, units=[_einheit(1)], template=_VORLAGE, store=store)
        assert text == "Der ganze Text."
        assert store.outline is None
        assert ("compose", None, None) in store.schritte

    async def test_ohne_eine_einzige_faktensammlung_bricht_der_lauf_ab(self):
        from src.limits import SUMMARY_READ_MAX_ATTEMPTS
        caller = _caller(["German"] + [RuntimeError("weg")] * SUMMARY_READ_MAX_ATTEMPTS)
        with pytest.raises(RuntimeError):
            await pl.run_pipeline(caller, units=[_einheit(1)], template=_VORLAGE, store=MemoryStore())


class TestEtappen:
    async def test_die_uhr_laesst_liegen_statt_zu_scheitern(self):
        store = MemoryStore()
        gefragt = {"n": 0}

        def stop():
            gefragt["n"] += 1
            return gefragt["n"] > 1

        caller = _caller(["German", "- A"])
        with pytest.raises(pl.PipelineInterrupted):
            await pl.run_pipeline(caller, units=[_einheit(1), _einheit(2), _einheit(3)],
                                  template=_VORLAGE, store=store, should_stop=stop)
        assert store.extractions == {"q1": "- A"}

    async def test_die_zweite_etappe_fragt_nur_die_uebrigen(self):
        store = MemoryStore()
        store.language = "German"
        store.extractions = {"q1": "- A"}
        caller = _caller(["- B", _PLAN, "Text A", "Text B", "Text C"])
        text = await pl.run_pipeline(caller, units=[_einheit(1), _einheit(2)],
                                     template=_VORLAGE, store=store)
        assert len(caller.client.gesendet) == 5
        assert "## C" in text

    async def test_geschriebene_abschnitte_werden_nicht_neu_geschrieben(self):
        store = MemoryStore()
        store.language = "German"
        store.extractions = {"q1": "- A"}
        store.outline = json.loads(_PLAN)
        store.sections = {0: "Text A", 1: "Text B"}
        caller = _caller(["Text C"])
        text = await pl.run_pipeline(caller, units=[_einheit(1)], template=_VORLAGE, store=store)
        assert len(caller.client.gesendet) == 1 and "Text A" in text and "Text C" in text

    async def test_eine_gescheiterte_einheit_wird_nicht_als_endgueltig_vermerkt(self):
        from src.limits import SUMMARY_READ_MAX_ATTEMPTS
        store = MemoryStore()
        caller = _caller(["German"] + [RuntimeError("weg")] * SUMMARY_READ_MAX_ATTEMPTS
                         + ["- B", _PLAN, "Text A", "Text B", "Text C"])
        await pl.run_pipeline(caller, units=[_einheit(1), _einheit(2)], template=_VORLAGE, store=store)
        assert store.extractions == {"q2": "- B"}


class TestHerzschlag:
    async def test_der_puls_schlaegt_waehrend_eines_langen_aufrufs(self, monkeypatch):
        monkeypatch.setattr(pl, "SUMMARY_HEARTBEAT_SECONDS", 0.01)

        class Langsam(FakeClient):
            async def create(self, *, model, messages, **kwargs):
                await asyncio.sleep(0.12)
                return await super().create(model=model, messages=messages, **kwargs)

        store = MemoryStore()
        caller = Caller(Langsam(["German", "- A", _PLAN, "Text A", "Text B", "Text C"]), "m")
        await pl.run_pipeline(caller, units=[_einheit(1)], template=_VORLAGE, store=store)
        assert store.pulse > 0
