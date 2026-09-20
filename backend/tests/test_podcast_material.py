"""Die Materialbeschaffung des Podcasts: Kaskade, Speicher mit Waechter, Rohquellen."""

import json

import pytest

from tests.podcast_helpers import FakeAsyncClient, fakten_antwort, quelle

from src.features.podcast import facts as fk
from src.features.podcast import instruction, source_text
from src.features.podcast.schemas import Person, PodcastParams
from src.services.facts import FACTS_FILE
from src.services.facts import store as fs
from src.tasks._stage import StageClock, StageLost
from src.tasks.podcast_tasks import _material
from src.tasks.podcast_tasks._shared import JobCancelled


def _params(**kw) -> PodcastParams:
    personen = [Person(name="Lena", role="host", voice_id="a"),
                Person(name="Jonas", role="expert", voice_id="b")]
    return PodcastParams(persons=personen, **kw)


@pytest.fixture
def ordner(monkeypatch):
    """Der Auftragsordner als Woerterbuch, dazu abgeschaltete Auftragsmeldungen."""
    dateien: dict[str, bytes] = {}
    monkeypatch.setattr(fs, "job_file_exists", lambda uid, job, name: name in dateien)
    monkeypatch.setattr(fs, "get_job_file", lambda uid, job, name: dateien[name])
    monkeypatch.setattr(fs, "save_job_file",
                        lambda uid, job, name, data: dateien.__setitem__(name, data))
    monkeypatch.setattr(fs.db, "update_job_status", lambda *a, **k: None)
    monkeypatch.setattr(fs.db, "touch_job_heartbeat", lambda *a: None)
    monkeypatch.setattr(_material, "assert_not_cancelled", lambda job: None)
    monkeypatch.setattr(_material, "still_mine", lambda job, versuch: True)
    return dateien


class TestRohquellen:
    def test_der_ganze_text_einer_quelle_kommt_bei_den_alten_wegen_an(self):
        quellen = [{"source_id": "doc_01", "filename": "a.pdf", "content": "Eins. Zwei. Drei."}]
        _name, stuecke = _material.as_chunks(quellen)[0]
        assert "".join(s["content"] for s in stuecke).count("Zwei.") >= 1
        assert "Drei." in "".join(s["content"] for s in stuecke)

    def test_jede_quelle_behaelt_ihren_namen(self):
        quellen = [{"source_id": "doc_01", "filename": "a.pdf", "content": "x" * 50},
                   {"source_id": "doc_02", "filename": "b.pdf", "content": "y" * 50}]
        assert [name for name, _ in _material.as_chunks(quellen)] == ["a.pdf", "b.pdf"]

    def test_eine_lange_quelle_wird_wieder_zerlegt(self):
        """Die aelteren Wege brauchen Einheiten, sonst faellt eine grosse Datei ganz weg."""
        lang = [{"source_id": "doc_01", "filename": "a.pdf", "content": "Satz. " * 20_000}]
        assert len(_material.as_chunks(lang)[0][1]) > 1

    def test_das_auffuellen_verwirft_die_hintere_quelle(self, monkeypatch):
        """Der Zustand, den die Fakten ersetzen: wer hinten steht, kommt nicht vor."""
        monkeypatch.setattr(
            "src.features.ai_assistant.tasks._context_budget.tool_context_budget",
            lambda: 3_000)
        quellen = [("vorne.pdf", source_text.to_pieces("v" * 10_000)),
                   ("hinten.pdf", source_text.to_pieces("h" * 10_000))]
        text = source_text.fit_to_budget(quellen)
        assert "vorne.pdf" in text and "hinten.pdf" not in text


class TestSpeicherMitWaechter:
    def test_die_fakten_landen_in_facts_json(self, ordner):
        speicher = _material.PodcastFactStore(7, "job-1", ["doc_01"], versuch=0)
        speicher.save_extraction("doc_01", [{"category": "c", "fact": "A", "citation": "b"}])
        assert FACTS_FILE in ordner
        assert json.loads(ordner[FACTS_FILE])["doc_01"][0]["fact"] == "A"

    def test_ein_abgebrochener_lauf_schreibt_nichts_mehr(self, ordner, monkeypatch):
        def _abgebrochen(job):
            raise JobCancelled()

        monkeypatch.setattr(_material, "assert_not_cancelled", _abgebrochen)
        speicher = _material.PodcastFactStore(7, "job-1", ["doc_01"], versuch=0)
        with pytest.raises(JobCancelled):
            speicher.save_extraction("doc_01", [{"category": "c", "fact": "A", "citation": "b"}])
        assert FACTS_FILE not in ordner

    def test_eine_abgegebene_etappe_schreibt_nichts_mehr(self, ordner, monkeypatch):
        monkeypatch.setattr(_material, "still_mine", lambda job, versuch: False)
        speicher = _material.PodcastFactStore(7, "job-1", ["doc_01"], versuch=0)
        with pytest.raises(StageLost):
            speicher.save_extraction("doc_01", [{"category": "c", "fact": "A", "citation": "b"}])
        assert FACTS_FILE not in ordner

    def test_lesen_bleibt_auch_dann_erlaubt(self, ordner, monkeypatch):
        monkeypatch.setattr(_material, "still_mine", lambda job, versuch: False)
        speicher = _material.PodcastFactStore(7, "job-1", ["doc_01"], versuch=0)
        assert speicher.load_extractions() == {}


class TestKaskade:
    """Gezielte Suche, sonst Fakten, darunter unveraendert Gliederung und Auffuellen."""

    async def test_die_fakten_gewinnen_ohne_anweisung(self):
        zahlen: dict = {}
        text = await instruction.build_context(
            [("a.pdf", [{"content": "roh"}])], "", None, None, zahlen,
            facts=lambda: _fertig("Fakten-Material"))
        assert text == "Fakten-Material" and zahlen["weg"] == instruction.FACTS

    async def test_ohne_fakten_geht_es_die_alten_wege(self):
        zahlen: dict = {}
        text = await instruction.build_context(
            [("a.pdf", [{"content": "roh"}])], "", None, None, zahlen,
            facts=lambda: _fertig(""))
        assert "roh" in text and zahlen["weg"] == instruction.FILL

    async def test_ohne_fakten_funktion_bleibt_alles_wie_vorher(self):
        """Die Route reicht keine Fakten herein, sie soll sich nicht anders verhalten."""
        zahlen: dict = {}
        text = await instruction.build_context(
            [("a.pdf", [{"content": "roh"}])], "", None, None, zahlen)
        assert "roh" in text and zahlen["weg"] == instruction.FILL

    async def test_eine_moegliche_suche_geht_den_fakten_vor(self, monkeypatch):
        """Der gemessene Weg bleibt oben: wer suchen kann, sucht."""
        gefragt = {"n": 0}

        async def _nie():
            gefragt["n"] += 1
            return "Fakten"

        async def _treffer(workspace_id, ids, anweisung):
            return [{"source_id": 1, "content": "Die gesuchte Stelle."}]

        _gezielt(monkeypatch)
        monkeypatch.setattr(instruction, "_ready_ids", lambda wid, uuids: [1])
        monkeypatch.setattr(instruction, "_probe", lambda wid, ids, anw: 0.2)
        monkeypatch.setattr(instruction, "_search", _treffer)
        monkeypatch.setattr(instruction, "_as_text", lambda chunks: "Die gesuchte Stelle.")

        zahlen: dict = {}
        text = await instruction.build_context(
            [("a.pdf", [{"content": "roh"}])], "nur Kapitel 3", 5, ["u1"], zahlen, facts=_nie)

        assert text == "Die gesuchte Stelle." and zahlen["weg"] == instruction.SEARCH
        assert gefragt["n"] == 0

    async def test_eine_gezielte_anweisung_ohne_modul_nimmt_die_fakten(self, monkeypatch):
        """Ein Upload hat nichts Durchsuchbares. Hier fiel der Zweig vorher aufs Auffuellen."""
        _gezielt(monkeypatch)
        zahlen: dict = {}
        text = await instruction.build_context(
            [("a.pdf", [{"content": "roh"}])], "nur Kapitel 3", None, None, zahlen,
            facts=lambda: _fertig("Fakten-Material"))
        assert text == "Fakten-Material" and zahlen["weg"] == instruction.FACTS

    async def test_eine_anweisung_neben_dem_material_nimmt_die_fakten(self, monkeypatch):
        """Und der Merker fuer die danebenliegende Anweisung bleibt trotzdem stehen."""
        _gezielt(monkeypatch)
        monkeypatch.setattr(instruction, "_ready_ids", lambda wid, uuids: [1])
        monkeypatch.setattr(instruction, "_probe", lambda wid, ids, anw: 0.99)

        zahlen: dict = {}
        text = await instruction.build_context(
            [("a.pdf", [{"content": "roh"}])], "etwas ganz anderes", 5, ["u1"], zahlen,
            facts=lambda: _fertig("Fakten-Material"))

        assert text == "Fakten-Material" and zahlen["weg"] == instruction.FACTS
        assert zahlen["daneben"] is True

    async def test_eine_leere_suche_nimmt_die_fakten(self, monkeypatch):
        async def _nichts(workspace_id, ids, anweisung):
            return []

        _gezielt(monkeypatch)
        monkeypatch.setattr(instruction, "_ready_ids", lambda wid, uuids: [1])
        monkeypatch.setattr(instruction, "_probe", lambda wid, ids, anw: 0.2)
        monkeypatch.setattr(instruction, "_search", _nichts)

        zahlen: dict = {}
        text = await instruction.build_context(
            [("a.pdf", [{"content": "roh"}])], "nur Kapitel 3", 5, ["u1"], zahlen,
            facts=lambda: _fertig("Fakten-Material"))
        assert text == "Fakten-Material" and zahlen["weg"] == instruction.FACTS


async def _fertig(text: str) -> str:
    return text


def _gezielt(monkeypatch) -> None:
    """Der Vor-Call ordnet die Anweisung als THEMA ein, ohne ein Modell zu fragen."""
    async def _art(anweisung):
        return instruction.SEARCH

    monkeypatch.setattr(instruction, "route", _art)


class TestGanzeMaterialphase:
    async def test_aus_zwei_quellen_wird_ein_faktenmaterial(self, ordner, monkeypatch):
        monkeypatch.setattr(fk, "material_budget", lambda: 120_000)
        client = FakeAsyncClient({"1.pdf": [fakten_antwort("Erstens")],
                                  "2.pdf": [fakten_antwort("Zweitens")]})
        monkeypatch.setattr(_material, "_llm", lambda: _FakeLLM(client))

        zahlen: dict = {}
        text = await _material._build(
            7, "job-1", {"sources": [quelle(1), quelle(2)]}, _params(),
            StageClock(), 0, zahlen)

        assert "Erstens" in text and "Zweitens" in text
        assert zahlen["weg"] == instruction.FACTS
        assert FACTS_FILE in ordner

    async def test_ein_gescheiterter_leser_faellt_auf_das_auffuellen(self, ordner, monkeypatch):
        monkeypatch.setattr(fk, "material_budget", lambda: 120_000)

        def _kaputt():
            raise RuntimeError("kein Anbieter")

        monkeypatch.setattr(_material, "_llm", _kaputt)
        zahlen: dict = {}
        text = await _material._build(
            7, "job-1", {"sources": [quelle(1, "Der rohe Text der Quelle.")]}, _params(),
            StageClock(), 0, zahlen)
        assert "Der rohe Text der Quelle." in text and zahlen["weg"] == instruction.FILL


class _FakeLLM:
    def __init__(self, client):
        self._async_client = client
        self._model = "m"
        self._provider = "fake"
