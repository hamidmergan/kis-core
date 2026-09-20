"""The Celery body: reading whole files, window and pages, stages, naming, progress."""

import io
import json

import pytest
from docx import Document

from tests.summary_helpers import FakeClient

from src.features.summary import pipeline as pl
from src.services.facts import store as fs
from src.services.model_limits import ModelProfile
from src.tasks import summary_tasks as st
from src.tasks._stage import StageContinue

_PLAN = json.dumps({"intro": "Vorweg.", "sections": [
    {"title": "A", "description": "a", "fact_ids": [1, 2]},
    {"title": "B", "description": "b", "fact_ids": []},
    {"title": "C", "description": "c", "fact_ids": []}]})
_PLAN_MIT_TITEL = json.dumps({"title": "Die neue Pruefungsordnung", "intro": "Vorweg.",
                              "sections": [
    {"title": "A", "description": "a", "fact_ids": [1, 2]},
    {"title": "B", "description": "b", "fact_ids": []},
    {"title": "C", "description": "c", "fact_ids": []}]})
_GRUPPE = "## A\nText A\n\n## B\nText B\n\n## C\nText C"
_ZUORDNUNG = json.dumps({"assignments": [{"fact_id": n, "section_index": n - 1}
                                         for n in (1, 2, 3)]})
_QUELLEN = [{"filename": "a.txt", "input_path": "p1"}]
# Die Sprache wird am Text gelesen, ein Test der sie prueft muss echten Text liefern.
_DEUTSCHER_TEXT = ("Die Lohnsteuer ist spaetestens am zehnten Tag nach Ablauf des "
                   "Anmeldungszeitraums abzufuehren. Wer eine gewerbliche Taetigkeit "
                   "aufnimmt, teilt dies der Gemeinde innerhalb eines Monats mit. ") * 3
_SPANISCHER_TEXT = ("El impuesto sobre la renta debe pagarse antes del decimo dia "
                    "siguiente al final del periodo de declaracion. Quien inicie una "
                    "actividad comercial debe informar al municipio en un mes. ") * 3
# Vor dem Ausschalten in der Vorrichtung festgehalten, ein Test braucht sie echt.
_ECHTE_SEITENPRUEFUNG = st._pages_or_raise


def _fakten(*aussagen: str) -> str:
    return json.dumps({"facts": [
        {"category": "figure", "fact": a, "citation": f"Beleg {a}"} for a in aussagen]})


def _profil(fenster: int) -> ModelProfile:
    return ModelProfile(window_tokens=fenster, source="gemessen", thinks=False, think_off="")


@pytest.fixture
def lauf(monkeypatch):
    dateien: dict[str, bytes] = {}
    zustand = {"status": [], "fortschritt": [], "ergebnis": None, "name": None, "geloescht": []}
    monkeypatch.setattr(st, "job_file_exists", lambda uid, job, name: name in dateien)
    monkeypatch.setattr(st, "save_job_file", lambda uid, job, name, data: dateien.__setitem__(name, data))
    # Die Auftragsdateien liest und schreibt seit dem Umzug der Fakten-Dienst.
    monkeypatch.setattr(fs, "job_file_exists", lambda uid, job, name: name in dateien)
    monkeypatch.setattr(fs, "get_job_file", lambda uid, job, name: dateien[name])
    monkeypatch.setattr(fs, "save_job_file", lambda uid, job, name, data: dateien.__setitem__(name, data))
    monkeypatch.setattr(st, "still_mine", lambda job, versuch: True)
    monkeypatch.setattr(st, "open_input_file",
                        lambda pfad, endung: __import__("contextlib").nullcontext("/tmp/x.txt"))
    monkeypatch.setattr(st, "read_text_layer", lambda pfad, ext: "wort " * 100)
    monkeypatch.setattr(st, "_pages_or_raise", lambda pfad, ext, name, locale: None)
    # Ohne Messung laeuft der Auftrag los, das ist der Normalfall dieser Tests.
    monkeypatch.setattr(st.window, "profile_for_choice", lambda provider_id: None)
    monkeypatch.setattr(st, "delete_file", lambda pfad: zustand["geloescht"].append(pfad))

    def _save_result_file(uid, job, endung, daten):
        zustand.setdefault("ergebnisse", []).append((endung, daten))
        zustand["ergebnis"] = daten
        return f"pfad{endung}"

    monkeypatch.setattr(st, "save_result_file", _save_result_file)
    monkeypatch.setattr(st, "save_result_and_evict",
                        lambda uid, job, pfad, name: zustand.__setitem__("name", name))
    monkeypatch.setattr(st.db, "get_job", lambda job: {"user_id": 1, "creator_locale": "de"})
    monkeypatch.setattr(st.db, "update_job_status",
                        lambda job, status, **k: (zustand["status"].append(status),
                                                  zustand["fortschritt"].append(k.get("progress"))))
    monkeypatch.setattr(st.db, "touch_job_heartbeat", lambda *a, **k: None)
    monkeypatch.setattr(pl, "facts_budget", lambda: 440_000)
    return dateien, zustand


def _modell(monkeypatch, antworten):
    client = FakeClient(antworten)
    traeger = type("K", (), {"_async_client": client, "_model": "m"})()
    import src.tasks.general_tasks as gt
    monkeypatch.setattr(gt, "_get_llm_client", lambda pid=None: traeger)
    monkeypatch.setattr(st, "log_llm_response", lambda *a, **k: None)
    return client


class TestEinDurchlauf:
    def test_ein_lauf_legt_das_ergebnis_ab(self, lauf, monkeypatch):
        dateien, zustand = lauf
        _modell(monkeypatch, [_fakten("Fakt"), _PLAN, _ZUORDNUNG, _GRUPPE])
        st._run_summary_inner("job", _QUELLEN, "kurzbriefing", None, 0)
        assert zustand["status"][-1] == "success"
        assert zustand["name"] == "a.md"
        assert dateien["summary.md"].decode("utf-8").startswith("Vorweg.")
        assert zustand["geloescht"] == ["p1"]

    def test_jede_datei_geht_ungeschnitten_in_den_auftrag(self, lauf, monkeypatch):
        dateien, _ = lauf
        _modell(monkeypatch, [_fakten("Fakt"), _PLAN, _ZUORDNUNG, _GRUPPE])
        st._run_summary_inner("job", _QUELLEN, "kurzbriefing", None, 0)
        quellen = json.loads(dateien["sources.json"])
        assert [q["source_id"] for q in quellen] == ["doc_01"]
        assert "part" not in quellen[0]

    def test_eine_fremde_vorlage_wird_abgelehnt(self, lauf):
        with pytest.raises(ValueError):
            st._run_summary_inner("job", _QUELLEN, "gibt_es_nicht", None, 0)

    def test_zu_wenig_text_sagt_es(self, lauf, monkeypatch):
        monkeypatch.setattr(st, "read_text_layer", lambda pfad, ext: "drei kurze Worte")
        with pytest.raises(ValueError) as fehler:
            st._run_summary_inner("job", _QUELLEN, "kurzbriefing", None, 0)
        assert "20" in str(fehler.value)


class TestDateigrenzeAusDemAdminbereich:
    """Wie viel Text ein Lese-Aufruf traegt, entscheidet die Einstellung, nicht der Code."""

    def test_eine_gesenkte_grenze_weist_die_grosse_datei_ab(self, lauf, monkeypatch):
        monkeypatch.setattr(st, "read_text_layer", lambda pfad, ext: "Wort " * 12_000)
        monkeypatch.setattr("src.database.get_setting",
                            lambda key, default="": "30000" if key.startswith("summary_") else default)

        with pytest.raises(ValueError) as fehler:
            st._run_summary_inner("job", _QUELLEN, "kurzbriefing", None, 0)

        assert "a.txt" in str(fehler.value)

    def test_dieselbe_datei_geht_bei_der_vollen_grenze_durch(self, lauf, monkeypatch):
        dateien, _ = lauf
        monkeypatch.setattr(st, "read_text_layer", lambda pfad, ext: "Wort " * 12_000)
        _modell(monkeypatch, [_fakten("Fakt"), _PLAN, _ZUORDNUNG, _GRUPPE])

        st._run_summary_inner("job", _QUELLEN, "kurzbriefing", None, 0)

        assert len(json.loads(dateien["sources.json"])) == 1


class TestFensterUndSeiten:
    """Was das Modell nicht am Stueck lesen kann, wird vor dem ersten Aufruf abgelehnt."""

    def test_ein_zu_kleines_fenster_lehnt_vor_dem_ersten_aufruf_ab(self, lauf, monkeypatch):
        monkeypatch.setattr(st, "read_text_layer", lambda pfad, ext: "Wort " * 60_000)
        monkeypatch.setattr(st.window, "profile_for_choice", lambda provider_id: _profil(20_080))
        client = _modell(monkeypatch, [])
        with pytest.raises(ValueError) as fehler:
            st._run_summary_inner("job", _QUELLEN, "kurzbriefing", None, 0)
        assert "a.txt" in str(fehler.value)
        assert client.gesendet == []

    def test_ein_grosses_fenster_laesst_dieselbe_datei_durch(self, lauf, monkeypatch):
        monkeypatch.setattr(st, "read_text_layer", lambda pfad, ext: "Wort " * 60_000)
        monkeypatch.setattr(st.window, "profile_for_choice", lambda provider_id: _profil(262_144))
        _, zustand = lauf
        _modell(monkeypatch, [_fakten("Fakt"), _PLAN, _ZUORDNUNG, _GRUPPE])
        st._run_summary_inner("job", _QUELLEN, "kurzbriefing", None, 0)
        assert zustand["status"][-1] == "success"

    def test_zu_viele_seiten_werden_abgelehnt(self, lauf, monkeypatch):
        import src.utils.file_validation as fv
        import src.services.tool_limits as tl
        monkeypatch.setattr(st, "_pages_or_raise", _ECHTE_SEITENPRUEFUNG)
        monkeypatch.setattr(fv, "count_pages", lambda ext, pfad: 250)
        monkeypatch.setattr(tl, "max_source_pages", lambda: 200)
        client = _modell(monkeypatch, [])
        with pytest.raises(ValueError) as fehler:
            st._run_summary_inner("job", _QUELLEN, "kurzbriefing", None, 0)
        assert "250" in str(fehler.value) and "a.txt" in str(fehler.value)
        assert client.gesendet == []


class TestMehrereQuellen:
    def test_zwei_dateien_werden_zu_einem_text(self, lauf, monkeypatch):
        dateien, zustand = lauf
        quellen = [{"filename": "a.txt", "input_path": "p1"},
                   {"filename": "b.txt", "input_path": "p2"}]
        texte = {"p1": "Wort " * 100, "p2": "Anderes Wort " * 100}
        monkeypatch.setattr(st, "open_input_file",
                            lambda pfad, endung: __import__("contextlib").nullcontext(pfad))
        monkeypatch.setattr(st, "read_text_layer", lambda pfad, ext: texte[pfad])
        _modell(monkeypatch, [_fakten("Fakt A"), _fakten("Fakt B"), _PLAN, _ZUORDNUNG,
                              _GRUPPE])
        st._run_summary_inner("job", quellen, "kurzbriefing", None, 0)
        gelesen = json.loads(dateien["sources.json"])
        assert [q["source_id"] for q in gelesen] == ["doc_01", "doc_02"]
        gemeldet = [f for f in zustand["fortschritt"] if f and f.get("step") == "map" and "total" in f]
        assert gemeldet and {f["total"] for f in gemeldet} == {2}
        assert zustand["name"] == "a und 1 weitere.md"


class TestEtappen:
    def test_die_zweite_etappe_liest_nur_die_uebrigen(self, lauf, monkeypatch):
        dateien, zustand = lauf
        quellen = [{"filename": "a.txt", "input_path": "p1"},
                   {"filename": "b.txt", "input_path": "p2"}]
        monkeypatch.setattr(st, "open_input_file",
                            lambda pfad, endung: __import__("contextlib").nullcontext(pfad))
        gefragt = {"n": 0}

        def abgelaufen(self):
            gefragt["n"] += 1
            return gefragt["n"] > 1

        monkeypatch.setattr(st.StageClock, "over", abgelaufen)
        _modell(monkeypatch, [_fakten("A")])
        with pytest.raises(StageContinue):
            st._run_summary_inner("job", quellen, "kurzbriefing", None, 0)
        gemerkt = json.loads(dateien["facts.json"])
        assert list(gemerkt) == ["doc_01"]
        assert [f["fact"] for f in gemerkt["doc_01"]] == ["A"]

        monkeypatch.setattr(st.StageClock, "over", lambda self: False)
        zweite = _modell(monkeypatch, [_fakten("B"), _PLAN, _ZUORDNUNG, _GRUPPE])
        st._run_summary_inner("job", quellen, "kurzbriefing", None, 0)
        # Lesen, planen, zuordnen und die drei Abschnitte in einem Aufruf.
        assert len(zweite.gesendet) == 4
        assert zustand["status"][-1] == "success"

    def test_die_quellenliste_bleibt_ueber_die_etappen_gleich(self, lauf, monkeypatch):
        dateien, _ = lauf
        monkeypatch.setattr(st.StageClock, "over", lambda self: True)
        _modell(monkeypatch, [])
        with pytest.raises(StageContinue):
            st._run_summary_inner("job", _QUELLEN, "kurzbriefing", None, 0)
        vorher = dateien["sources.json"]
        monkeypatch.setattr(st, "read_text_layer", lambda pfad, ext: "ganz anderer Text " * 50)
        monkeypatch.setattr(st.StageClock, "over", lambda self: False)
        _modell(monkeypatch, [_fakten("A"), _PLAN, _ZUORDNUNG, _GRUPPE])
        st._run_summary_inner("job", _QUELLEN, "kurzbriefing", None, 0)
        assert dateien["sources.json"] == vorher

    def test_die_zweite_etappe_meldet_kein_lesen_mehr(self, lauf, monkeypatch):
        dateien, zustand = lauf
        monkeypatch.setattr(st.StageClock, "over", lambda self: True)
        _modell(monkeypatch, [])
        with pytest.raises(StageContinue):
            st._run_summary_inner("job", _QUELLEN, "kurzbriefing", None, 0)
        zustand["fortschritt"].clear()
        monkeypatch.setattr(st.StageClock, "over", lambda self: False)
        _modell(monkeypatch, [_fakten("Fakt"), _PLAN, _ZUORDNUNG, _GRUPPE])
        st._run_summary_inner("job", _QUELLEN, "kurzbriefing", None, 0)
        assert all((f or {}).get("step") != "extract" for f in zustand["fortschritt"])

    def test_das_fertige_ergebnis_wird_nicht_neu_geschrieben(self, lauf, monkeypatch):
        dateien, zustand = lauf
        dateien["summary.md"] = "Schon fertig.".encode("utf-8")
        client = _modell(monkeypatch, [])
        st._run_summary_inner("job", _QUELLEN, "kurzbriefing", None, 0)
        assert client.gesendet == [] and zustand["status"][-1] == "success"


class TestBeschaedigteDateien:
    def test_kaputte_sources_json_wird_neu_gelesen(self, lauf, monkeypatch):
        dateien, zustand = lauf
        dateien["sources.json"] = b"{das ist kein json"
        _modell(monkeypatch, [_fakten("Fakt"), _PLAN, _ZUORDNUNG, _GRUPPE])
        st._run_summary_inner("job", _QUELLEN, "kurzbriefing", None, 0)
        assert zustand["status"][-1] == "success"
        assert [q["source_id"] for q in json.loads(dateien["sources.json"])] == ["doc_01"]

    def test_kaputte_facts_json_beginnt_von_vorn(self, lauf, monkeypatch):
        dateien, zustand = lauf
        dateien["facts.json"] = b"{das ist kein json"
        _modell(monkeypatch, [_fakten("Fakt"), _PLAN, _ZUORDNUNG, _GRUPPE])
        st._run_summary_inner("job", _QUELLEN, "kurzbriefing", None, 0)
        assert zustand["status"][-1] == "success"
        gemerkt = json.loads(dateien["facts.json"])
        assert [f["fact"] for f in gemerkt["doc_01"]] == ["Fakt"]

    def test_kaputte_outline_json_wird_neu_geplant(self, lauf, monkeypatch):
        dateien, zustand = lauf
        dateien["outline.json"] = b"{das ist kein json"
        _modell(monkeypatch, [_fakten("Fakt"), _PLAN, _ZUORDNUNG, _GRUPPE])
        st._run_summary_inner("job", _QUELLEN, "kurzbriefing", None, 0)
        assert zustand["status"][-1] == "success"
        assert json.loads(dateien["outline.json"])["intro"] == "Vorweg."


class TestWordDatei:
    def test_markdown_und_word_werden_beide_abgelegt(self, lauf, monkeypatch):
        dateien, zustand = lauf
        _modell(monkeypatch, [_fakten("Fakt"), _PLAN, _ZUORDNUNG, _GRUPPE])
        st._run_summary_inner("job", _QUELLEN, "kurzbriefing", None, 0)
        endungen = [endung for endung, _ in zustand["ergebnisse"]]
        assert endungen == [".md", ".docx"]
        wort_bytes = dict(zustand["ergebnisse"])[".docx"]
        doc = Document(io.BytesIO(wort_bytes))
        assert doc.paragraphs[0].text == "a"
        assert "updateFields" in doc.settings.element.xml

    def test_ein_fehler_bei_der_wortdatei_wirft_den_auftrag_nicht_um(self, lauf, monkeypatch):
        dateien, zustand = lauf
        monkeypatch.setattr(st, "markdown_to_docx",
                            lambda text, **k: (_ for _ in ()).throw(RuntimeError("kaputt")))
        _modell(monkeypatch, [_fakten("Fakt"), _PLAN, _ZUORDNUNG, _GRUPPE])
        st._run_summary_inner("job", _QUELLEN, "kurzbriefing", None, 0)
        assert zustand["status"][-1] == "success"
        endungen = [endung for endung, _ in zustand["ergebnisse"]]
        assert endungen == [".md"]
        assert dateien["summary.md"].decode("utf-8").startswith("Vorweg.")

    def test_eine_zeitgrenze_waehrend_der_wortdatei_wird_nicht_verschluckt(self, lauf, monkeypatch):
        from celery.exceptions import SoftTimeLimitExceeded
        monkeypatch.setattr(st, "markdown_to_docx",
                            lambda text, **k: (_ for _ in ()).throw(SoftTimeLimitExceeded()))
        _modell(monkeypatch, [_fakten("Fakt"), _PLAN, _ZUORDNUNG, _GRUPPE])
        with pytest.raises(SoftTimeLimitExceeded):
            st._run_summary_inner("job", _QUELLEN, "kurzbriefing", None, 0)


class TestNamensgebung:
    """Der Titel kommt aus dem Gliederungsaufruf, ein eigener Aufruf dafuer gibt es nicht."""

    def test_der_titel_der_gliederung_benennt_die_datei(self, lauf, monkeypatch):
        _, zustand = lauf
        _modell(monkeypatch, [_fakten("Fakt"), _PLAN_MIT_TITEL, _ZUORDNUNG, _GRUPPE])
        st._run_summary_inner("job", _QUELLEN, "kurzbriefing", None, 0)
        assert zustand["name"] == "Die neue Pruefungsordnung.md"

    def test_der_titel_steht_auch_auf_dem_deckblatt_der_wortdatei(self, lauf, monkeypatch):
        _, zustand = lauf
        _modell(monkeypatch, [_fakten("Fakt"), _PLAN_MIT_TITEL, _ZUORDNUNG, _GRUPPE])
        st._run_summary_inner("job", _QUELLEN, "kurzbriefing", None, 0)
        doc = Document(io.BytesIO(dict(zustand["ergebnisse"])[".docx"]))
        assert doc.paragraphs[0].text == "Die neue Pruefungsordnung"

    def test_mehrere_dateien_bekommen_trotzdem_den_einen_titel(self, lauf, monkeypatch):
        _, zustand = lauf
        quellen = [{"filename": "a.txt", "input_path": "p1"},
                   {"filename": "b.txt", "input_path": "p2"}]
        monkeypatch.setattr(st, "open_input_file",
                            lambda pfad, endung: __import__("contextlib").nullcontext(pfad))
        monkeypatch.setattr(st, "read_text_layer", lambda pfad, ext: "wort " * 100)
        _modell(monkeypatch, [_fakten("A"), _fakten("B"), _PLAN_MIT_TITEL, _ZUORDNUNG,
                              _GRUPPE])
        st._run_summary_inner("job", quellen, "kurzbriefing", None, 0)
        assert zustand["name"] == "Die neue Pruefungsordnung.md"

    def test_ohne_titel_bleibt_es_beim_namen_der_quelle(self, lauf, monkeypatch):
        _, zustand = lauf
        _modell(monkeypatch, [_fakten("Fakt"), _PLAN, _ZUORDNUNG, _GRUPPE])
        st._run_summary_inner("job", _QUELLEN, "kurzbriefing", None, 0)
        assert zustand["name"] == "a.md"

    def test_ein_fertiger_text_ohne_ueberschrift_wird_aus_der_gliederung_benannt(
            self, lauf, monkeypatch):
        """Eine Vorlage ohne Ueberschriften laesst den Titel aus dem Text, der Plan hat ihn."""
        dateien, zustand = lauf
        dateien["summary.md"] = b"Vorweg.\n\nText ohne jede Ueberschrift."
        dateien["outline.json"] = json.dumps({"title": "Fristen im Sommersemester",
                                              "intro": "Vorweg.", "sections": []}).encode()
        _modell(monkeypatch, [])
        st._run_summary_inner("job", _QUELLEN, "kurzbriefing", None, 0)
        assert zustand["name"] == "Fristen im Sommersemester.md"


class TestTitelSaeuberung:
    def test_was_in_keinen_dateinamen_darf_faellt_weg(self):
        assert st._clean_title('Recht: Paragraf 5/7 <neu>?') == "Recht Paragraf 5 7 neu"

    def test_ein_langer_titel_wird_am_wort_gekuerzt(self):
        titel = st._clean_title("Wort " * 40)
        assert len(titel) <= st._TITLE_MAX_CHARS
        assert titel.endswith("Wort")

    def test_ein_titel_aus_lauter_verbotenem_zaehlt_als_keiner(self):
        assert st._clean_title("///") == ""
        assert st._result_name(["a.txt"], "///") == "a.md"

    def test_eine_fuehrende_raute_und_leerraum_verschwinden(self):
        assert st._clean_title("#  Der   Titel  ") == "Der Titel"


class TestSpracheDerWortdatei:
    """Der Hinweis auf dem Deckblatt folgt dem Dokument, nicht der Oberflaeche des Nutzers."""

    def _gemerkte_sprache(self, monkeypatch) -> dict:
        gemerkt: dict = {}

        def _bauen(text, **k):
            gemerkt.update(k)
            return b"docx"

        monkeypatch.setattr(st, "markdown_to_docx", _bauen)
        return gemerkt

    def test_ein_deutsches_dokument_bekommt_deutsch(self, lauf, monkeypatch):
        gemerkt = self._gemerkte_sprache(monkeypatch)
        monkeypatch.setattr(st, "read_text_layer", lambda pfad, ext: _DEUTSCHER_TEXT)
        _modell(monkeypatch, [_fakten("Fakt"), _PLAN, _ZUORDNUNG, _GRUPPE])
        st._run_summary_inner("job", _QUELLEN, "kurzbriefing", None, 0)
        assert gemerkt["locale"] == "de"

    def test_ein_spanisches_dokument_bekommt_englisch(self, lauf, monkeypatch):
        gemerkt = self._gemerkte_sprache(monkeypatch)
        monkeypatch.setattr(st, "read_text_layer", lambda pfad, ext: _SPANISCHER_TEXT)
        _modell(monkeypatch, [_fakten("Fakt"), _PLAN, _ZUORDNUNG, _GRUPPE])
        st._run_summary_inner("job", _QUELLEN, "kurzbriefing", None, 0)
        assert gemerkt["locale"] == "en"

    def test_eine_unerkannte_sprache_nimmt_die_des_nutzers(self, lauf, monkeypatch):
        dateien, _ = lauf
        gemerkt = self._gemerkte_sprache(monkeypatch)
        monkeypatch.setattr(st.db, "get_job",
                            lambda job: {"user_id": 1, "creator_locale": "en"})
        dateien["language.txt"] = pl.LANGUAGE_FALLBACK.encode()
        _modell(monkeypatch, [_fakten("Fakt"), _PLAN, _ZUORDNUNG, _GRUPPE])
        st._run_summary_inner("job", _QUELLEN, "kurzbriefing", None, 0)
        assert gemerkt["locale"] == "en"
