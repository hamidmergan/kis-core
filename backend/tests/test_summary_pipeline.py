"""One run end to end, with the store in memory and the model faked."""

import asyncio
import json

import pytest

from tests.summary_helpers import FakeAntwort, FakeClient, MemoryStore

from src.features.summary import pipeline as pl
from src.features.summary import reading as rd
from src.features.summary.models import Caller
from src.features.summary.templates import get_template
from src.limits import (
    SUMMARY_FACTS_MAX_CHARS,
    SUMMARY_FACTS_MIN_CHARS,
    SUMMARY_READ_MAX_FACTS,
)
from src.services.model_limits import CHARS_PER_TOKEN

_PLAN = json.dumps({"intro": "Vorweg.", "sections": [
    {"title": "A", "description": "a", "fact_ids": [1]},
    {"title": "B", "description": "b", "fact_ids": [2]},
    {"title": "C", "description": "c", "fact_ids": [3]}]})
_GRUPPE = "## A\nText A\n\n## B\nText B\n\n## C\nText C"
_ZUORDNUNG = json.dumps({"assignments": [{"fact_id": n, "section_index": n - 1}
                                         for n in (1, 2, 3)]})
_VORLAGE = get_template("kurzbriefing")


def _quelle(nr):
    return {"source_id": f"doc_{nr:02d}", "filename": f"{nr}.pdf", "content": "X" * 50}


def _fakten(*aussagen: str) -> str:
    return json.dumps({"facts": [
        {"category": "figure", "fact": a, "citation": f"Beleg {a}"} for a in aussagen]})


def _caller(antworten):
    return Caller(FakeClient(antworten), "m")


class _Abgewiesen(Exception):
    def __init__(self, status: int = 429):
        super().__init__("zu viel")
        self.status_code = status


@pytest.fixture(autouse=True)
def _kein_budget_aus_der_datenbank(monkeypatch):
    monkeypatch.setattr(pl, "facts_budget", lambda: 440_000)
    # Eine flache Antwortliste hat keine Zuordnung zur Datei. Laufen mehrere Aufrufe
    # zugleich, entscheidet das Wettrennen, welche Antwort welche Datei bekommt. Die
    # Nebenlaeufigkeit wird deshalb dort geprueft, wo die Antworten je Datei kommen.
    monkeypatch.setattr(pl.cfg, "map_concurrency", lambda: 1)
    monkeypatch.setattr(pl.cfg, "facts_cap", lambda: SUMMARY_READ_MAX_FACTS)
    monkeypatch.setattr(rd, "SUMMARY_RETRY_DELAY_SECONDS", 0)
    monkeypatch.setattr(pl, "SUMMARY_RETRY_DELAY_SECONDS", 0)
    rd._schema_mode_supported = True


class TestFaktenDeckel:
    """Eine Datei, ein Aufruf. Der Deckel begrenzt, was dieser eine Aufruf liefern darf."""

    def test_eine_quelle_von_zehn_bekommt_ihren_anteil(self):
        assert pl.read_max_facts(10) == 33

    def test_der_deckel_begrenzt_ein_grosses_budget(self, monkeypatch):
        monkeypatch.setattr(pl, "facts_per_source", lambda quellen: 30_000)
        assert pl.read_max_facts(10) == SUMMARY_READ_MAX_FACTS


class TestFaktenAnteil:
    def test_eine_quelle_bekommt_den_hoechstwert(self):
        assert pl.facts_per_source(1) == SUMMARY_FACTS_MAX_CHARS

    def test_viele_quellen_teilen_sich_das_budget(self):
        assert pl.facts_per_source(100) == 4_400

    def test_unter_den_mindestwert_geht_es_nie(self):
        assert pl.facts_per_source(1000) == SUMMARY_FACTS_MIN_CHARS


_DEUTSCH = ("Die Lohnsteuer ist spaetestens am zehnten Tag nach Ablauf des "
            "Anmeldungszeitraums abzufuehren. Wer eine gewerbliche Taetigkeit aufnimmt, "
            "teilt dies der Gemeinde innerhalb eines Monats mit. Die Aufbewahrungsfrist "
            "fuer Buecher und Aufzeichnungen betraegt zehn Jahre.")
_ENGLISCH = ("The employer shall pay the withheld tax by the tenth day after the end of "
             "the reporting period. Anyone taking up a commercial activity must notify "
             "the municipality within one month. Books and records are kept for ten years.")


class TestSprache:
    def test_die_probe_kommt_aus_der_mitte(self):
        text = "A" * 5000 + "MITTE" + "B" * 5000
        assert "MITTE" in pl.language_sample(text, 400)

    def test_deutscher_text_wird_ohne_modell_erkannt(self):
        assert pl.detect_language(_DEUTSCH) == "German"

    def test_englischer_text_wird_ohne_modell_erkannt(self):
        assert pl.detect_language(_ENGLISCH) == "English"

    def test_zu_wenig_text_bleibt_bei_der_umschreibung(self):
        # Unter der Mindestlaenge wird gar nicht erst geraten.
        assert pl.detect_language("X" * 50) == pl.LANGUAGE_FALLBACK

    def test_ganz_ohne_text_bleibt_die_umschreibung(self):
        assert pl.detect_language("") == pl.LANGUAGE_FALLBACK


class TestEinLauf:
    async def test_die_sprache_kostet_keinen_aufruf(self):
        # Lesen, Gliederung, Zuordnung, Schreiben. Kein Aufruf mehr fuer die Sprache.
        caller = _caller([_fakten("A"), _PLAN, _ZUORDNUNG, _GRUPPE])

        await pl.run_pipeline(caller, sources=[_quelle(1)], template=_VORLAGE,
                              store=MemoryStore())

        assert len(caller.client.gesendet) == 4

    async def test_ein_ganzer_lauf_in_reihenfolge(self):
        store = MemoryStore()
        caller = _caller([_fakten("A"), _fakten("B"), _PLAN, _ZUORDNUNG, _GRUPPE])

        text = await pl.run_pipeline(caller, sources=[_quelle(1), _quelle(2)],
                                     template=_VORLAGE, store=store)

        assert text.startswith("Vorweg.") and "## A\n\nText A" in text and "## C" in text
        assert store.language == pl.LANGUAGE_FALLBACK
        assert [f["fact"] for f in store.extractions["doc_01"]] == ["A"]
        assert [f["fact"] for f in store.extractions["doc_02"]] == ["B"]
        assert store.outline["intro"] == "Vorweg."
        assert store.sections == {0: "Text A", 1: "Text B", 2: "Text C"}
        assert ("outline", None, None) in store.schritte
        assert ("section", 3, 3) in store.schritte

    async def test_jede_quelle_geht_in_genau_einen_aufruf(self):
        caller = _caller([_fakten("A"), _fakten("B"), _fakten("C"), _PLAN, _ZUORDNUNG, _GRUPPE])
        await pl.run_pipeline(caller, sources=[_quelle(1), _quelle(2), _quelle(3)],
                              template=_VORLAGE, store=MemoryStore())
        gelesen = caller.client.user_prompts()[0:3]
        assert sorted(p.split("(")[1].split(")")[0] for p in gelesen) == \
            ["1.pdf", "2.pdf", "3.pdf"]

    async def test_jede_quelle_bekommt_ihren_anteil_und_die_vorlage(self, monkeypatch):
        monkeypatch.setattr(pl, "facts_budget", lambda: 24_000)
        caller = _caller([_fakten("A"), _fakten("B"), _fakten("C"), _PLAN, _ZUORDNUNG, _GRUPPE])
        await pl.run_pipeline(caller, sources=[_quelle(1), _quelle(2), _quelle(3)],
                              template=_VORLAGE, store=MemoryStore())
        from src.features.summary import reading as lesen
        fakten = 8_000 // lesen.CHARS_PER_FACT
        erwartet = int(fakten * lesen._ANSWER_CHARS_PER_FACT / CHARS_PER_TOKEN)
        assert [o.get("max_tokens") for o in caller.client.optionen[0:3]] == [erwartet] * 3
        assert "briefing" in caller.client.system_prompts()[0].lower()

    async def test_die_gliederung_bekommt_den_numerierten_vorrat(self):
        caller = _caller([_fakten("A"), _fakten("B"), _PLAN, _ZUORDNUNG, _GRUPPE])
        await pl.run_pipeline(caller, sources=[_quelle(1), _quelle(2)],
                              template=_VORLAGE, store=MemoryStore())
        vorrat = caller.client.user_prompts()[2]
        assert "#1 (figure) [1.pdf] A" in vorrat and "#2 (figure) [2.pdf] B" in vorrat

    async def test_eine_unlesbare_gliederung_faellt_auf_den_einzelaufruf_zurueck(self, monkeypatch):
        from src.features.summary import writing as wr
        monkeypatch.setattr(wr, "SUMMARY_RETRY_DELAY_SECONDS", 0)
        store = MemoryStore()
        caller = _caller([_fakten("A"), "nix", "nix", "Der ganze Text."])
        text = await pl.run_pipeline(caller, sources=[_quelle(1)], template=_VORLAGE, store=store)
        assert text == "Der ganze Text."
        assert store.outline is None
        assert ("compose", None, None) in store.schritte

    async def test_ohne_eine_einzige_faktensammlung_bricht_der_lauf_ab(self):
        from src.limits import SUMMARY_READ_MAX_ATTEMPTS
        caller = _caller([RuntimeError("weg")] * SUMMARY_READ_MAX_ATTEMPTS)
        with pytest.raises(RuntimeError):
            await pl.run_pipeline(caller, sources=[_quelle(1)], template=_VORLAGE,
                                  store=MemoryStore())


class TestNebenlaeufigkeit:
    """Drei Aufrufe zugleich, eine Absage wird an Ort und Stelle wiederholt.

    Gemessen 20.09.: bei drei bleibt der langsamste Aufruf bei 161s und damit 139s unter
    der Grenze des Anbieters, bei fuenf sind es 205s und nur noch 95s Puffer.
    """

    class _NachDatei(FakeClient):
        """Antworten je Datei, sonst entscheidet bei parallelen Aufrufen das Wettrennen."""

        def __init__(self, je_datei: dict, sonst: list):
            super().__init__(sonst)
            self._je_datei = {name: list(w) for name, w in je_datei.items()}
            self.gleichzeitig = 0
            self.hoechststand = 0
            self.hoechststand_erfolg = 0

        async def create(self, *, model, messages, **kwargs):
            datei = next((n for n in self._je_datei if f"({n})" in messages[-1]["content"]), None)
            if datei is None:
                return await super().create(model=model, messages=messages, **kwargs)
            self.gesendet.append(messages)
            self.optionen.append(kwargs)
            self.gleichzeitig += 1
            self.hoechststand = max(self.hoechststand, self.gleichzeitig)
            try:
                await asyncio.sleep(0.01)
                naechste = self._je_datei[datei].pop(0)
                if isinstance(naechste, Exception):
                    raise naechste
                # Nur gelungene Aufrufe zaehlen, ihr Hoechststand zeigt die echte Staffelung.
                self.hoechststand_erfolg = max(self.hoechststand_erfolg, self.gleichzeitig)
                return FakeAntwort(naechste)
            finally:
                self.gleichzeitig -= 1

    def _lauf(self, je_datei, fakten):
        """Nach dem Plan folgt die Zuordnung, erst danach werden die Abschnitte geschrieben."""
        plan = json.dumps({"intro": "Vorweg.", "sections": [
            {"title": "A", "description": "a"}, {"title": "B", "description": "b"},
            {"title": "C", "description": "c"}]})
        zuordnung = json.dumps({"assignments": [{"fact_id": n, "section_index": 0}
                                                for n in range(1, fakten + 1)]})
        client = self._NachDatei(je_datei, [plan, zuordnung, _GRUPPE])
        return client, Caller(client, "m")

    async def test_drei_aufrufe_sind_zugleich_unterwegs(self, monkeypatch):
        monkeypatch.setattr(pl.cfg, "map_concurrency", lambda: 3)
        client, caller = self._lauf({f"{i}.pdf": [_fakten("A")] for i in range(1, 5)}, 4)
        await pl.run_pipeline(caller, sources=[_quelle(i) for i in range(1, 5)],
                              template=_VORLAGE, store=MemoryStore())
        assert client.hoechststand == 3

    async def test_die_staffelung_kommt_aus_dem_adminbereich(self, monkeypatch):
        """Nicht der Wert im Code entscheidet, sondern der eingestellte."""
        monkeypatch.setattr("src.database.get_setting", lambda key, default="": "2")
        # Die Fixture haelt die Staffelung sonst auf eins fest.
        monkeypatch.setattr(pl.cfg, "map_concurrency",
                            lambda: pl.cfg.value_of("summary_map_concurrency"))
        client, caller = self._lauf({f"{i}.pdf": [_fakten("A")] for i in range(1, 5)}, 4)

        await pl.run_pipeline(caller, sources=[_quelle(i) for i in range(1, 5)],
                              template=_VORLAGE, store=MemoryStore())

        assert client.hoechststand == 2

    async def test_ueber_drei_hinaus_wird_gewartet(self, monkeypatch):
        monkeypatch.setattr(pl.cfg, "map_concurrency", lambda: 3)
        client, caller = self._lauf({f"{i}.pdf": [_fakten("A")] for i in range(1, 8)}, 7)
        await pl.run_pipeline(caller, sources=[_quelle(i) for i in range(1, 8)],
                              template=_VORLAGE, store=MemoryStore())
        assert client.hoechststand == 3

    async def test_was_fertig_ist_bleibt_wenn_die_uhr_ablaeuft(self, monkeypatch):
        """Ein abgeschlossenes Paket wird gespeichert, auch wenn die Etappe danach endet."""
        gefragt = {"n": 0}

        def stop():
            gefragt["n"] += 1
            return gefragt["n"] > 3

        client, caller = self._lauf({f"{i}.pdf": [_fakten("A")] for i in range(1, 8)}, 7)
        store = MemoryStore()
        with pytest.raises(pl.PipelineInterrupted):
            await pl.run_pipeline(caller, sources=[_quelle(i) for i in range(1, 8)],
                                  template=_VORLAGE, store=store, should_stop=stop)
        assert store.extractions

    async def test_eine_absage_wird_an_ort_und_stelle_nachgeholt(self, monkeypatch):
        """Ein abgewiesenes Paket wird wiederholt, bevor das naechste an die Reihe kommt."""
        monkeypatch.setattr(pl, "SUMMARY_RETRY_DELAY_SECONDS", 0)
        client, caller = self._lauf(
            {f"{i}.pdf": [_Abgewiesen(429), _fakten("A")] for i in range(1, 4)}, 3)
        store = MemoryStore()
        await pl.run_pipeline(caller, sources=[_quelle(i) for i in range(1, 4)],
                              template=_VORLAGE, store=store)
        # Kein Paket faellt durch die Absage weg, jedes wird an seiner Stelle nachgeholt.
        assert len(store.extractions) == 3

    async def test_nach_der_absage_waechst_die_wartezeit(self, monkeypatch):
        monkeypatch.setattr(pl, "SUMMARY_RETRY_DELAY_SECONDS", 3)
        monkeypatch.setattr(pl, "SUMMARY_HEARTBEAT_SECONDS", 3600)
        gewartet: list[float] = []
        echt = asyncio.sleep

        async def _merken(dauer, *rest):
            gewartet.append(dauer)
            await echt(0)

        monkeypatch.setattr(pl.asyncio, "sleep", _merken)
        client, caller = self._lauf(
            {"1.pdf": [_Abgewiesen(503), _Abgewiesen(429), _fakten("A")]}, 1)
        await pl.run_pipeline(caller, sources=[_quelle(1)], template=_VORLAGE,
                              store=MemoryStore())
        assert [d for d in gewartet if 1 <= d < 100] == [3, 6]

    async def test_eine_dauerhaft_abgewiesene_datei_wird_ausgelassen(self, monkeypatch):
        from src.limits import SUMMARY_READ_MAX_ATTEMPTS
        monkeypatch.setattr(pl.cfg, "map_concurrency", lambda: 3)
        client, caller = self._lauf(
            {"1.pdf": [_Abgewiesen(429)] * (SUMMARY_READ_MAX_ATTEMPTS + 1),
             "2.pdf": [_fakten("B")]}, 2)
        store = MemoryStore()
        await pl.run_pipeline(caller, sources=[_quelle(1), _quelle(2)],
                              template=_VORLAGE, store=store)
        assert list(store.extractions) == ["doc_02"]


class TestEtappen:
    async def test_die_uhr_laesst_liegen_statt_zu_scheitern(self, monkeypatch):
        store = MemoryStore()
        gefragt = {"n": 0}

        def stop():
            gefragt["n"] += 1
            return gefragt["n"] > 1

        caller = _caller([_fakten("A")])
        with pytest.raises(pl.PipelineInterrupted):
            await pl.run_pipeline(caller, sources=[_quelle(1), _quelle(2), _quelle(3)],
                                  template=_VORLAGE, store=store, should_stop=stop)
        assert list(store.extractions) == ["doc_01"]

    async def test_die_zweite_etappe_fragt_nur_die_uebrigen(self):
        store = MemoryStore()
        store.language = "German"
        store.extractions = {"doc_01": [{"category": "c", "fact": "A", "citation": "b"}]}
        caller = _caller([_fakten("B"), _PLAN, _ZUORDNUNG, _GRUPPE])
        text = await pl.run_pipeline(caller, sources=[_quelle(1), _quelle(2)],
                                     template=_VORLAGE, store=store)
        # Lesen, planen, zuordnen und die drei Abschnitte in einem Aufruf.
        assert len(caller.client.gesendet) == 4
        assert "## C" in text

    async def test_geschriebene_abschnitte_werden_nicht_neu_geschrieben(self):
        store = MemoryStore()
        store.language = "German"
        store.extractions = {"doc_01": [{"category": "c", "fact": "A", "citation": "b"}]}
        store.outline = json.loads(_PLAN)
        store.outline["sections"] = [dict(s, scope=s["description"])
                                     for s in store.outline["sections"]]
        store.sections = {0: "Text A", 1: "Text B"}
        caller = _caller(["Text C"])
        text = await pl.run_pipeline(caller, sources=[_quelle(1)], template=_VORLAGE, store=store)
        assert len(caller.client.gesendet) == 1 and "Text A" in text and "Text C" in text

    async def test_eine_gescheiterte_datei_wird_nicht_als_endgueltig_vermerkt(self, monkeypatch):
        from src.limits import SUMMARY_READ_MAX_ATTEMPTS
        store = MemoryStore()
        caller = _caller([RuntimeError("weg")] * SUMMARY_READ_MAX_ATTEMPTS
                         + [_fakten("B"), _PLAN, _ZUORDNUNG, _GRUPPE])
        await pl.run_pipeline(caller, sources=[_quelle(1), _quelle(2)],
                              template=_VORLAGE, store=store)
        assert list(store.extractions) == ["doc_02"]


class TestHerzschlag:
    async def test_der_puls_schlaegt_waehrend_eines_langen_aufrufs(self, monkeypatch):
        monkeypatch.setattr(pl, "SUMMARY_HEARTBEAT_SECONDS", 0.01)

        class Langsam(FakeClient):
            async def create(self, *, model, messages, **kwargs):
                await asyncio.sleep(0.12)
                return await super().create(model=model, messages=messages, **kwargs)

        store = MemoryStore()
        caller = Caller(Langsam([_fakten("A"), _PLAN, _ZUORDNUNG, _GRUPPE]), "m")
        await pl.run_pipeline(caller, sources=[_quelle(1)], template=_VORLAGE, store=store)
        assert store.pulse > 0
