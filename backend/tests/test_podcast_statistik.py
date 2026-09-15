"""Die Zahlen zum Podcast-Lauf: welchen Weg das Material nahm und was danach passierte."""

import pytest

from src.features.podcast import instruction
from src.routes.jobs._shared import _format_job_rows
from src.services.job_statistik import anbieter_und_modelle, messe_vorab, notiere
from src.storage import load_result_meta, save_result_meta


UID = 7
JOB = "c" * 32


def _quellen():
    return [("a.pdf", [{"content": "Erster Abschnitt"}, {"content": "Zweiter Abschnitt"}])]


def _budget(monkeypatch, chars=100_000):
    import src.features.ai_assistant.tasks._context_budget as budget
    monkeypatch.setattr(budget, "tool_context_budget", lambda: chars)


def _nah(monkeypatch, abstand=0.0):
    """Die Anweisung steckt im Material, die Abstandsmessung haelt nicht auf."""
    monkeypatch.setattr(instruction, "_probe", lambda ws, ids, anweisung: abstand)


def _vorcall(monkeypatch, antwort):
    monkeypatch.setattr(instruction, "_llm", lambda: object())

    async def _fake(llm, anweisung):
        return antwort

    monkeypatch.setattr(instruction, "_classify", _fake)


class TestWegDesMaterials:
    @pytest.mark.asyncio
    async def test_leere_anweisung_meldet_auffuellen(self, monkeypatch):
        _budget(monkeypatch)
        zahlen: dict = {}

        await instruction.build_context(_quellen(), "", 42, ["s1"], zahlen)

        assert zahlen["weg"] == instruction.FILL

    @pytest.mark.asyncio
    async def test_gezielte_anweisung_meldet_suche_mit_fundstellen(self, monkeypatch):
        _budget(monkeypatch)
        _vorcall(monkeypatch, instruction.SEARCH)
        _nah(monkeypatch)
        monkeypatch.setattr(instruction, "_ready_ids", lambda ws, uuids: [7])

        async def _treffer(workspace_id, ids, anweisung):
            return [{"source_id": 7, "content": "Die Stelle zur Kuehlung"}]

        monkeypatch.setattr(instruction, "_search", _treffer)
        monkeypatch.setattr(instruction.db, "get_aia_source_by_id",
                            lambda sid: {"filename": "a.pdf"})
        zahlen: dict = {}

        await instruction.build_context(_quellen(), "Kuehlung", 42, ["s1"], zahlen)

        assert zahlen["weg"] == instruction.SEARCH
        assert zahlen["stellen"] == 1

    @pytest.mark.asyncio
    async def test_gescheiterte_suche_meldet_auffuellen(self, monkeypatch):
        _budget(monkeypatch)
        _vorcall(monkeypatch, instruction.SEARCH)
        _nah(monkeypatch)
        monkeypatch.setattr(instruction, "_ready_ids", lambda ws, uuids: [7])

        async def _kaputt(workspace_id, ids, anweisung):
            raise RuntimeError("Einbettungsdienst weg")

        monkeypatch.setattr(instruction, "_search", _kaputt)
        zahlen: dict = {}

        await instruction.build_context(_quellen(), "Kuehlung", 42, ["s1"], zahlen)

        assert zahlen["weg"] == instruction.FILL, "jeder Rueckfall ist ein Auffuellen"

    @pytest.mark.asyncio
    async def test_gliederung_meldet_ihren_eigenen_weg(self, monkeypatch):
        _budget(monkeypatch)

        async def _breit(sources, workspace_id, source_uuids):
            return "Die verdichtete Fassung"

        monkeypatch.setattr(instruction, "_broad_context", _breit)
        zahlen: dict = {}

        text = await instruction.build_context(_quellen(), "", 42, ["s1"], zahlen)

        assert text == "Die verdichtete Fassung"
        assert zahlen["weg"] == instruction.OUTLINE


class TestMesseVorab:
    def test_misst_ohne_zu_schreiben(self, lokal):
        zahlen: dict = {"herkunft": "files"}

        with messe_vorab(zahlen):
            pass

        assert zahlen["dauer_s"] >= 0
        assert load_result_meta(UID, JOB) is None, "ohne Auftrag darf nichts geschrieben werden"

    def test_haelt_den_fehler_fest(self, lokal):
        zahlen: dict = {}

        with pytest.raises(RuntimeError):
            with messe_vorab(zahlen):
                raise RuntimeError("Datei unlesbar")

        assert zahlen["fehler"] == "Datei unlesbar"
        assert "dauer_s" in zahlen


class TestSchlussmeta:
    def test_ueberschreibt_die_zahlen_nicht(self, lokal):
        notiere(UID, JOB, "vertonung", {"beitraege": 21})

        # So wie _render.py die Schlussmeta schreibt: erst laden, dann ergaenzen.
        save_result_meta(UID, JOB, {
            **(load_result_meta(UID, JOB) or {}),
            "seconds": 167.0,
            "lines": 21,
        })

        meta = load_result_meta(UID, JOB)
        assert meta["seconds"] == 167.0
        assert meta["stats"]["vertonung"] == {"beitraege": 21}


class TestAnbieterUndModelle:
    def test_fasst_mehrere_anbieter_ohne_doppel_zusammen(self, monkeypatch):
        import src.services.job_statistik as statistik

        namen = {1: "myLab", 2: "Kokoro"}
        monkeypatch.setattr(statistik, "anbieter_und_modell", lambda pid, feature: {
            "anbieter": namen[pid], "modell": "tts-1", "route": feature,
        })

        kennung = anbieter_und_modelle([1, 2, 1], "tts")

        assert kennung == {"anbieter": "myLab, Kokoro", "modell": "tts-1", "route": "tts"}

    def test_leere_namen_fallen_weg(self, monkeypatch):
        import src.services.job_statistik as statistik

        monkeypatch.setattr(statistik, "anbieter_und_modell", lambda pid, feature: {
            "anbieter": "", "modell": "", "route": feature,
        })

        assert anbieter_und_modelle([1], "tts") == {
            "anbieter": "", "modell": "", "route": "tts"}


class TestJobzeile:
    def _zeile(self, status: str = "success") -> dict:
        from datetime import datetime
        return {
            "job_uuid": JOB, "user_id": UID, "tool": "podcast",
            "original_filename": "folge.mp3", "status": status, "error_message": None,
            "progress": None, "result_path": "", "result_filename": "folge.mp3",
            "created_at": datetime(2026, 9, 15, 9, 0, 0), "started_at": None,
            "completed_at": None, "render_started_at": None, "render_queued_at": None,
            "expires_at": None,
        }

    def test_admin_sieht_die_podcast_zahlen(self, lokal):
        notiere(UID, JOB, "vertonung", {"beitraege": 21})

        zeilen = _format_job_rows([self._zeile()], "de", is_admin=True)

        assert zeilen[0]["meta"]["stats"]["vertonung"] == {"beitraege": 21}

    def test_nutzer_sieht_die_podcast_zahlen_nicht(self, lokal):
        save_result_meta(UID, JOB, {"seconds": 167.0})
        notiere(UID, JOB, "vertonung", {"beitraege": 21})

        zeilen = _format_job_rows([self._zeile()], "de", is_admin=False)

        assert "stats" not in zeilen[0]["meta"]
        assert zeilen[0]["meta"]["seconds"] == 167.0


class TestStatusabfrage:
    """Auch der Einzelabruf eines Auftrags gibt die Zahlen nur an Admins."""

    def _job(self) -> dict:
        return {
            "job_uuid": JOB, "user_id": UID, "tool": "podcast", "status": "success",
            "error_message": None, "progress": None, "result_path": "/tmp/folge.mp3",
            "result_filename": "folge.mp3",
        }

    def _frage(self, monkeypatch, nutzer: dict):
        from src import database as db
        from src.routes.jobs import _status

        monkeypatch.setattr(db, "get_job", lambda _uuid: self._job())
        return _status.get_job_status(JOB, nutzer, "de")

    def test_admin_bekommt_die_zahlen(self, lokal, monkeypatch):
        notiere(UID, JOB, "vertonung", {"beitraege": 21})

        antwort = self._frage(monkeypatch, {"user_id": UID, "role": "admin"})

        assert antwort["meta"]["stats"]["vertonung"] == {"beitraege": 21}

    def test_nutzer_bekommt_die_zahlen_nicht(self, lokal, monkeypatch):
        save_result_meta(UID, JOB, {"seconds": 167.0})
        notiere(UID, JOB, "vertonung", {"beitraege": 21})

        antwort = self._frage(monkeypatch, {"user_id": UID, "role": "user"})

        assert "stats" not in antwort["meta"]
        assert antwort["meta"]["seconds"] == 167.0


class TestAbstandInDenZahlen:
    @pytest.mark.asyncio
    async def test_anweisung_neben_dem_material_meldet_auffuellen(self, monkeypatch):
        _budget(monkeypatch)
        _vorcall(monkeypatch, instruction.SEARCH)
        _nah(monkeypatch, instruction.MAX_DIST + 0.05)
        monkeypatch.setattr(instruction, "_ready_ids", lambda ws, uuids: [7])
        zahlen: dict = {}

        await instruction.build_context(
            _quellen(), "Sprich ueber Katzen und Hunde", 42, ["s1"], zahlen)

        assert zahlen["weg"] == instruction.FILL
        assert zahlen["daneben"] is True
        assert "stellen" not in zahlen
