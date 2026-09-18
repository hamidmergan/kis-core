"""The Celery body: reading, splitting, stages, naming, progress in files not parts."""

import json

import pytest

from tests.summary_helpers import FakeClient

from src.features.summary import pipeline as pl
from src.tasks import summary_tasks as st
from src.tasks._stage import StageContinue

_PLAN = json.dumps({"intro": "Vorweg.", "sections": [
    {"title": "A", "scope": "a"}, {"title": "B", "scope": "b"}, {"title": "C", "scope": "c"}]})
_QUELLEN = [{"filename": "a.txt", "input_path": "p1"}]


@pytest.fixture
def lauf(monkeypatch):
    dateien: dict[str, bytes] = {}
    zustand = {"status": [], "fortschritt": [], "ergebnis": None, "name": None, "geloescht": []}
    monkeypatch.setattr(st, "job_file_exists", lambda uid, job, name: name in dateien)
    monkeypatch.setattr(st, "get_job_file", lambda uid, job, name: dateien[name])
    monkeypatch.setattr(st, "save_job_file", lambda uid, job, name, data: dateien.__setitem__(name, data))
    monkeypatch.setattr(st, "still_mine", lambda job, versuch: True)
    monkeypatch.setattr(st, "open_input_file",
                        lambda pfad, endung: __import__("contextlib").nullcontext("/tmp/x.txt"))
    monkeypatch.setattr(st, "read_text_layer", lambda pfad, ext: "wort " * 100)
    monkeypatch.setattr(st, "part_size_for_chat", lambda: 70_000)
    monkeypatch.setattr(st, "delete_file", lambda pfad: zustand["geloescht"].append(pfad))
    monkeypatch.setattr(st, "save_result_file",
                        lambda uid, job, endung, daten: zustand.__setitem__("ergebnis", daten) or "pfad.md")
    monkeypatch.setattr(st, "save_result_and_evict",
                        lambda uid, job, pfad, name: zustand.__setitem__("name", name))
    monkeypatch.setattr(st.db, "get_job", lambda job: {"user_id": 1, "creator_locale": "de"})
    monkeypatch.setattr(st.db, "update_job_status",
                        lambda job, status, **k: (zustand["status"].append(status),
                                                  zustand["fortschritt"].append(k.get("progress"))))
    monkeypatch.setattr(st.db, "touch_job_heartbeat", lambda *a, **k: None)
    monkeypatch.setattr(pl, "facts_budget", lambda: 440_000)
    monkeypatch.setattr(pl, "SUMMARY_MAP_CONCURRENCY", 1)
    return dateien, zustand


def _modell(monkeypatch, antworten):
    client = FakeClient(antworten)
    traeger = type("K", (), {"_async_client": client, "_model": "m"})()
    import src.tasks.general_tasks as gt
    monkeypatch.setattr(gt, "_get_llm_client", lambda pid=None: traeger)
    monkeypatch.setattr(st, "log_llm_response", lambda *a, **k: None)
    return client


def _lange_datei(monkeypatch, teile=3):
    text = "\n".join(f"§ {n} Vorschrift\n" + ("Wort " * 200) for n in range(1, 61))
    grenze = len(text) // teile + 100
    monkeypatch.setattr(st, "read_text_layer", lambda pfad, ext: text)
    monkeypatch.setattr(st, "part_size_for_chat", lambda: grenze)


class TestEinDurchlauf:
    def test_ein_lauf_legt_das_ergebnis_ab(self, lauf, monkeypatch):
        dateien, zustand = lauf
        _modell(monkeypatch, ["German", "- Fakt", _PLAN, "Text A", "Text B", "Text C"])
        st._run_summary_inner("job", _QUELLEN, "kurzbriefing", None, 0)
        assert zustand["status"][-1] == "success"
        assert zustand["name"] == "a.md"
        assert dateien["summary.md"].decode("utf-8").startswith("Vorweg.")
        assert zustand["geloescht"] == ["p1"]

    def test_eine_fremde_vorlage_wird_abgelehnt(self, lauf):
        with pytest.raises(ValueError):
            st._run_summary_inner("job", _QUELLEN, "gibt_es_nicht", None, 0)

    def test_zu_wenig_text_sagt_es(self, lauf, monkeypatch):
        monkeypatch.setattr(st, "read_text_layer", lambda pfad, ext: "drei kurze Worte")
        with pytest.raises(ValueError) as fehler:
            st._run_summary_inner("job", _QUELLEN, "kurzbriefing", None, 0)
        assert "20" in str(fehler.value)


class TestGeteilteDatei:
    def test_aus_einer_langen_datei_werden_einheiten(self, lauf, monkeypatch):
        dateien, zustand = lauf
        _lange_datei(monkeypatch)
        _modell(monkeypatch, ["German", "- A", "- B", "- C", _PLAN, "Text A", "Text B", "Text C"])
        st._run_summary_inner("job", _QUELLEN, "kurzbriefing", None, 0)
        einheiten = json.loads(dateien["sources.json"])
        assert [e["source_id"] for e in einheiten] == ["q1t1", "q1t2", "q1t3"]
        assert zustand["name"] == "a.md"

    def test_der_fortschritt_zaehlt_dateien_nicht_teile(self, lauf, monkeypatch):
        _, zustand = lauf
        _lange_datei(monkeypatch)
        _modell(monkeypatch, ["German", "- A", "- B", "- C", _PLAN, "Text A", "Text B", "Text C"])
        st._run_summary_inner("job", _QUELLEN, "kurzbriefing", None, 0)
        gemeldet = [f for f in zustand["fortschritt"] if f and f.get("step") == "map" and "total" in f]
        assert gemeldet and {f["total"] for f in gemeldet} == {1} and max(f["part"] for f in gemeldet) == 1

    def test_zu_viele_teile_werden_abgelehnt(self, lauf, monkeypatch):
        monkeypatch.setattr(st, "SUMMARY_MAX_PARTS_PER_JOB", 2)
        _lange_datei(monkeypatch)
        with pytest.raises(ValueError) as fehler:
            st._run_summary_inner("job", _QUELLEN, "kurzbriefing", None, 0)
        assert "2" in str(fehler.value)


class TestEtappen:
    def test_die_zweite_etappe_liest_nur_die_uebrigen_teile(self, lauf, monkeypatch):
        dateien, zustand = lauf
        _lange_datei(monkeypatch)
        gefragt = {"n": 0}

        def abgelaufen(self):
            gefragt["n"] += 1
            return gefragt["n"] > 1

        monkeypatch.setattr(st.StageClock, "over", abgelaufen)
        _modell(monkeypatch, ["German", "- A"])
        with pytest.raises(StageContinue):
            st._run_summary_inner("job", _QUELLEN, "kurzbriefing", None, 0)
        assert json.loads(dateien["facts.json"]) == {"q1t1": "- A"}

        monkeypatch.setattr(st.StageClock, "over", lambda self: False)
        zweite = _modell(monkeypatch, ["- B", "- C", _PLAN, "Text A", "Text B", "Text C"])
        st._run_summary_inner("job", _QUELLEN, "kurzbriefing", None, 0)
        assert len(zweite.gesendet) == 6
        assert zustand["status"][-1] == "success"

    def test_die_aufteilung_bleibt_ueber_die_etappen_gleich(self, lauf, monkeypatch):
        dateien, _ = lauf
        _lange_datei(monkeypatch)
        monkeypatch.setattr(st.StageClock, "over", lambda self: True)
        _modell(monkeypatch, ["German"])
        with pytest.raises(StageContinue):
            st._run_summary_inner("job", _QUELLEN, "kurzbriefing", None, 0)
        vorher = dateien["sources.json"]
        monkeypatch.setattr(st, "part_size_for_chat", lambda: 500)
        monkeypatch.setattr(st.StageClock, "over", lambda self: False)
        _modell(monkeypatch, ["- A", "- B", "- C", _PLAN, "Text A", "Text B", "Text C"])
        st._run_summary_inner("job", _QUELLEN, "kurzbriefing", None, 0)
        assert dateien["sources.json"] == vorher

    def test_die_zweite_etappe_meldet_kein_lesen_mehr(self, lauf, monkeypatch):
        dateien, zustand = lauf
        monkeypatch.setattr(st.StageClock, "over", lambda self: True)
        _modell(monkeypatch, ["German"])
        with pytest.raises(StageContinue):
            st._run_summary_inner("job", _QUELLEN, "kurzbriefing", None, 0)
        zustand["fortschritt"].clear()
        monkeypatch.setattr(st.StageClock, "over", lambda self: False)
        _modell(monkeypatch, ["- Fakt", _PLAN, "Text A", "Text B", "Text C"])
        st._run_summary_inner("job", _QUELLEN, "kurzbriefing", None, 0)
        assert all((f or {}).get("step") != "extract" for f in zustand["fortschritt"])

    def test_das_fertige_ergebnis_wird_nicht_neu_geschrieben(self, lauf, monkeypatch):
        dateien, zustand = lauf
        dateien["summary.md"] = "Schon fertig.".encode("utf-8")
        client = _modell(monkeypatch, [])
        st._run_summary_inner("job", _QUELLEN, "kurzbriefing", None, 0)
        assert client.gesendet == [] and zustand["status"][-1] == "success"
