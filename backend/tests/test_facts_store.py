"""Das Speicher-Protokoll des Fakten-Dienstes: facts.json, Waechter, Fortschritt, Herzschlag."""

import asyncio
import json

import pytest

from tests.facts_helpers import MemoryFactStore, fakten

from src.services.facts import FACTS_FILE, JobFactStore, keepalive
from src.services.facts import store as fs


@pytest.fixture
def ordner(monkeypatch):
    """Der Auftragsordner als Woerterbuch, dazu die Meldungen an den Auftrag."""
    dateien: dict[str, bytes] = {}
    meldungen: dict = {"fortschritt": [], "pulse": 0}
    monkeypatch.setattr(fs, "job_file_exists", lambda uid, job, name: name in dateien)
    monkeypatch.setattr(fs, "get_job_file", lambda uid, job, name: dateien[name])
    monkeypatch.setattr(fs, "save_job_file",
                        lambda uid, job, name, data: dateien.__setitem__(name, data))
    monkeypatch.setattr(fs.db, "update_job_status",
                        lambda job, status, **k: meldungen["fortschritt"].append(k.get("progress")))
    monkeypatch.setattr(fs.db, "touch_job_heartbeat",
                        lambda job: meldungen.__setitem__("pulse", meldungen["pulse"] + 1))
    return dateien, meldungen


def _speicher(ids=("doc_01", "doc_02"), guard=None) -> JobFactStore:
    return JobFactStore(1, "job-uuid-1234", list(ids), guard=guard)


class TestAuftragsdateien:
    def test_eine_fehlende_datei_gibt_nichts(self, ordner):
        assert fs.read_job_text(1, "job", "weg.txt") is None

    def test_eine_geschriebene_datei_kommt_zurueck(self, ordner):
        fs.write_job_text(1, "job", "a.txt", "Hallo")
        assert fs.read_job_text(1, "job", "a.txt") == "Hallo"

    def test_eine_unlesbare_datei_zaehlt_als_fehlend(self, ordner, monkeypatch):
        dateien, _ = ordner
        dateien["a.txt"] = b"x"

        def _kaputt(uid, job, name):
            raise OSError("Ablage weg")

        monkeypatch.setattr(fs, "get_job_file", _kaputt)
        assert fs.read_job_text(1, "job", "a.txt") is None

    def test_kaputtes_json_faellt_auf_den_ersatzwert(self):
        assert fs.parse_job_json("job", "a.json", "{kein json", {"leer": True}) == {"leer": True}

    def test_leerer_inhalt_faellt_auf_den_ersatzwert(self):
        assert fs.parse_job_json("job", "a.json", None, []) == []

    def test_gutes_json_kommt_als_objekt(self):
        assert fs.parse_job_json("job", "a.json", '{"a": 1}', None) == {"a": 1}


class TestFaktenSpeicher:
    def test_die_fakten_ueberstehen_den_neustart(self, ordner):
        _speicher().save_extraction("doc_01", fakten("A"))
        # Ein frischer Speicher desselben Auftrags, so wie ihn die naechste Etappe baut.
        gelesen = _speicher().load_extractions()
        assert [f["fact"] for f in gelesen["doc_01"]] == ["A"]

    def test_sie_liegen_in_facts_json(self, ordner):
        dateien, _ = ordner
        _speicher().save_extraction("doc_01", fakten("A"))
        assert FACTS_FILE in dateien
        assert json.loads(dateien[FACTS_FILE])["doc_01"][0]["fact"] == "A"

    def test_eine_zweite_quelle_verdraengt_die_erste_nicht(self, ordner):
        speicher = _speicher()
        speicher.save_extraction("doc_01", fakten("A"))
        speicher.save_extraction("doc_02", fakten("B"))
        assert sorted(_speicher().load_extractions()) == ["doc_01", "doc_02"]

    def test_ohne_datei_ist_der_vorrat_leer(self, ordner):
        assert _speicher().load_extractions() == {}

    def test_eine_kaputte_datei_beginnt_von_vorn(self, ordner):
        dateien, _ = ordner
        dateien[FACTS_FILE] = b"{halb geschrieben"
        assert _speicher().load_extractions() == {}

    def test_umlaute_bleiben_lesbar(self, ordner):
        dateien, _ = ordner
        _speicher().save_extraction("doc_01", fakten("Pruefungsausschuss trifft Maßnahmen"))
        assert "Maßnahmen" in dateien[FACTS_FILE].decode("utf-8")


class TestWaechter:
    def test_der_waechter_verhindert_das_schreiben(self, ordner):
        dateien, _ = ordner

        def _weg():
            raise RuntimeError("Etappe gehoert nicht mehr uns")

        with pytest.raises(RuntimeError):
            _speicher(guard=_weg).save_extraction("doc_01", fakten("A"))
        assert FACTS_FILE not in dateien

    def test_der_waechter_wird_beim_lesen_nicht_gefragt(self, ordner):
        """Lesen kostet nichts und darf auch einer verlorenen Etappe nicht verwehrt werden."""
        gefragt = {"n": 0}

        def _zaehlen():
            gefragt["n"] += 1

        _speicher(guard=_zaehlen).load_extractions()
        assert gefragt["n"] == 0

    def test_der_waechter_schuetzt_auch_den_herzschlag(self, ordner):
        def _weg():
            raise RuntimeError("weg")

        with pytest.raises(RuntimeError):
            _speicher(guard=_weg).heartbeat()

    def test_ohne_waechter_wird_geschrieben(self, ordner):
        dateien, _ = ordner
        _speicher().save_extraction("doc_01", fakten("A"))
        assert FACTS_FILE in dateien


class TestFortschritt:
    def test_die_map_phase_zaehlt_die_gelesenen_quellen(self, ordner):
        _, meldungen = ordner
        speicher = _speicher(["doc_01", "doc_02", "doc_03"])
        speicher.save_extraction("doc_01", fakten("A"))
        assert meldungen["fortschritt"][-1] == {"step": "map", "part": 1, "total": 3}

    def test_der_zaehler_waechst_mit_jeder_quelle(self, ordner):
        _, meldungen = ordner
        speicher = _speicher(["doc_01", "doc_02"])
        speicher.save_extraction("doc_01", fakten("A"))
        speicher.save_extraction("doc_02", fakten("B"))
        assert meldungen["fortschritt"][-1] == {"step": "map", "part": 2, "total": 2}

    def test_eine_unbekannte_quelle_zaehlt_nicht_mit(self, ordner):
        """Gezaehlt werden die hochgeladenen Quellen, nicht was sonst im Ordner landet."""
        _, meldungen = ordner
        speicher = _speicher(["doc_01"])
        speicher.save_extraction("doc_09", fakten("X"))
        assert meldungen["fortschritt"][-1] == {"step": "map", "part": 0, "total": 1}

    def test_ein_eigener_schritt_geht_unveraendert_durch(self, ordner):
        _, meldungen = ordner
        _speicher().progress("outline", 2, 5)
        assert meldungen["fortschritt"][-1] == {"step": "outline", "part": 2, "total": 5}

    def test_ein_schritt_ohne_zahlen_meldet_nur_den_schritt(self, ordner):
        _, meldungen = ordner
        _speicher().progress("compose")
        assert meldungen["fortschritt"][-1] == {"step": "compose"}

    def test_jede_meldung_ist_auch_ein_herzschlag(self, ordner):
        _, meldungen = ordner
        _speicher().progress("compose")
        assert meldungen["pulse"] == 1

    def test_der_herzschlag_allein_meldet_sich_auch(self, ordner):
        _, meldungen = ordner
        _speicher().heartbeat()
        assert meldungen["pulse"] == 1


class TestHerzschlag:
    async def test_der_puls_schlaegt_waehrend_eines_langen_aufrufs(self):
        speicher = MemoryFactStore()
        async with keepalive(speicher, 0.01):
            await asyncio.sleep(0.08)
        assert speicher.pulse > 0

    async def test_nach_dem_block_schlaegt_er_nicht_mehr(self):
        speicher = MemoryFactStore()
        async with keepalive(speicher, 0.01):
            await asyncio.sleep(0.05)
        stand = speicher.pulse
        await asyncio.sleep(0.05)
        assert speicher.pulse == stand

    async def test_ein_kurzer_block_kostet_keinen_schlag(self):
        speicher = MemoryFactStore()
        async with keepalive(speicher, 3600):
            await asyncio.sleep(0)
        assert speicher.pulse == 0

    async def test_ein_fehlschlag_beendet_den_puls_ohne_den_lauf_zu_stuerzen(self):
        class _Kaputt(MemoryFactStore):
            def heartbeat(self):
                raise RuntimeError("Datenbank weg")

        speicher = _Kaputt()
        async with keepalive(speicher, 0.01):
            await asyncio.sleep(0.05)
        assert speicher.pulse == 0

    async def test_ein_fehler_im_block_kommt_durch(self):
        """Der Puls raeumt sich ab, der Fehler des Laufs bleibt der Fehler des Laufs."""
        speicher = MemoryFactStore()
        with pytest.raises(ValueError):
            async with keepalive(speicher, 0.01):
                raise ValueError("Lauf gescheitert")
