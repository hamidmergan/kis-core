"""Die Anweisung entscheidet den Weg: auffuellen oder gezielt suchen."""

import pytest

from src.features.podcast import instruction


@pytest.fixture
def kein_vorcall(monkeypatch):
    """Der Vor-Call darf in keinem Test wirklich ein Modell fragen."""
    gefragt = []

    def _nie(*args, **kwargs):
        raise AssertionError("der Vor-Call haette nicht laufen duerfen")

    monkeypatch.setattr(instruction, "_llm", _nie)
    return gefragt


def _vorcall(monkeypatch, antwort):
    """Der Vor-Call antwortet mit einem festen Weg, ohne Modell."""
    gefragt = []
    monkeypatch.setattr(instruction, "_llm", lambda: object())

    async def _fake(llm, anweisung):
        gefragt.append(anweisung)
        return antwort

    monkeypatch.setattr(instruction, "_classify", _fake)
    return gefragt


def _quellen():
    return [("a.pdf", [{"content": "Erster Abschnitt"}, {"content": "Zweiter Abschnitt"}])]


def _budget(monkeypatch, chars=100_000):
    import src.features.ai_assistant.tasks._context_budget as budget
    monkeypatch.setattr(budget, "tool_context_budget", lambda tool="": chars)


class TestWegwahl:
    @pytest.mark.asyncio
    async def test_leere_anweisung_fragt_kein_modell(self, kein_vorcall):
        assert await instruction.route("") == instruction.FILL
        assert await instruction.route("   ") == instruction.FILL

    @pytest.mark.asyncio
    async def test_stil_anweisung_landet_beim_auffuellen(self, monkeypatch):
        _vorcall(monkeypatch, instruction.FILL)
        assert await instruction.route("halte es einfach") == instruction.FILL

    @pytest.mark.asyncio
    async def test_themen_anweisung_wird_als_solche_erkannt(self, monkeypatch):
        gefragt = _vorcall(monkeypatch, instruction.SEARCH)
        assert await instruction.route("sprich ueber die Kuehlung") == instruction.SEARCH
        assert gefragt == ["sprich ueber die Kuehlung"]

    @pytest.mark.asyncio
    async def test_ohne_anbieter_wird_aufgefuellt_statt_zu_scheitern(self, monkeypatch):
        def _kaputt():
            raise RuntimeError("kein Anbieter")

        monkeypatch.setattr(instruction, "_llm", _kaputt)
        assert await instruction.route("sprich ueber die Kuehlung") == instruction.FILL


class TestKontext:
    @pytest.mark.asyncio
    async def test_leere_anweisung_fuellt_auf(self, monkeypatch, kein_vorcall):
        _budget(monkeypatch)
        text = await instruction.build_context(_quellen(), "", 42, ["s1"])
        assert "Erster Abschnitt" in text and "Zweiter Abschnitt" in text

    @pytest.mark.asyncio
    async def test_stil_anweisung_fuellt_auf(self, monkeypatch):
        _budget(monkeypatch)
        _vorcall(monkeypatch, instruction.FILL)
        gesucht = []
        monkeypatch.setattr(instruction, "_search", lambda *a: gesucht.append(a))
        text = await instruction.build_context(_quellen(), "halte es einfach", 42, ["s1"])
        assert "Erster Abschnitt" in text
        assert gesucht == [], "eine Stil-Anweisung darf nicht suchen"

    @pytest.mark.asyncio
    async def test_ohne_einbettungen_faellt_sie_still_zurueck(self, monkeypatch):
        _budget(monkeypatch)
        _vorcall(monkeypatch, instruction.SEARCH)
        monkeypatch.setattr(instruction, "_ready_ids", lambda ws, uuids: [])
        gesucht = []
        monkeypatch.setattr(instruction, "_search", lambda *a: gesucht.append(a))
        text = await instruction.build_context(_quellen(), "sprich ueber X", 42, ["s1"])
        assert "Erster Abschnitt" in text
        assert gesucht == [], "ohne Einbettungen darf keine Suche starten"

    @pytest.mark.asyncio
    async def test_gezielte_anweisung_nimmt_die_gefundenen_stellen(self, monkeypatch):
        _budget(monkeypatch)
        _vorcall(monkeypatch, instruction.SEARCH)
        monkeypatch.setattr(instruction, "_ready_ids", lambda ws, uuids: [7])

        async def _treffer(workspace_id, ids, anweisung):
            return [{"source_id": 7, "content": "Die Stelle zur Kuehlung"}]

        monkeypatch.setattr(instruction, "_search", _treffer)
        monkeypatch.setattr(instruction.db, "get_aia_source_by_id",
                            lambda sid: {"filename": "a.pdf"})
        text = await instruction.build_context(_quellen(), "Kuehlung", 42, ["s1"])
        assert "Die Stelle zur Kuehlung" in text
        assert "# a.pdf" in text
        assert "Zweiter Abschnitt" not in text, "die Suche ersetzt das Auffuellen"

    @pytest.mark.asyncio
    async def test_suche_ohne_treffer_faellt_zurueck(self, monkeypatch):
        _budget(monkeypatch)
        _vorcall(monkeypatch, instruction.SEARCH)
        monkeypatch.setattr(instruction, "_ready_ids", lambda ws, uuids: [7])

        async def _nichts(workspace_id, ids, anweisung):
            return []

        monkeypatch.setattr(instruction, "_search", _nichts)
        text = await instruction.build_context(_quellen(), "Kuehlung", 42, ["s1"])
        assert "Erster Abschnitt" in text

    @pytest.mark.asyncio
    async def test_kaputte_suche_wirft_den_podcast_nicht_weg(self, monkeypatch):
        _budget(monkeypatch)
        _vorcall(monkeypatch, instruction.SEARCH)
        monkeypatch.setattr(instruction, "_ready_ids", lambda ws, uuids: [7])

        async def _kaputt(workspace_id, ids, anweisung):
            raise RuntimeError("Einbettungsdienst weg")

        monkeypatch.setattr(instruction, "_search", _kaputt)
        text = await instruction.build_context(_quellen(), "Kuehlung", 42, ["s1"])
        assert "Erster Abschnitt" in text

    @pytest.mark.asyncio
    async def test_ohne_modul_wird_nur_aufgefuellt(self, monkeypatch):
        _budget(monkeypatch)
        _vorcall(monkeypatch, instruction.SEARCH)
        gesucht = []
        monkeypatch.setattr(instruction, "_search", lambda *a: gesucht.append(a))
        text = await instruction.build_context(_quellen(), "Kuehlung", None, None)
        assert "Erster Abschnitt" in text
        assert gesucht == []


class TestAntwortLesen:
    """Der Vor-Call liefert JSON, ein Denk-Modell stellt seine Gedanken davor."""

    def test_liest_die_art(self):
        assert instruction._read_art('{"art": "THEMA"}') == "THEMA"
        assert instruction._read_art('{"art": "stil"}') == "STIL"

    def test_ueberliest_gedanken_und_zaun(self):
        roh = '<think>Das klingt nach Ton</think>```json\n{"art": "STIL"}\n```'
        assert instruction._read_art(roh) == "STIL"

    def test_unlesbares_ist_keine_art(self):
        assert instruction._read_art("") == ""
        assert instruction._read_art("keine Ahnung") == ""
        assert instruction._read_art("{kaputt") == ""


class TestFertigeQuellen:
    def test_nimmt_nur_fertig_indexierte_aus_demselben_modul(self, monkeypatch):
        zeilen = {
            "fertig": {"id": 1, "workspace_id": 42, "status": "ready"},
            "laeuft": {"id": 2, "workspace_id": 42, "status": "pending"},
            "fremd": {"id": 3, "workspace_id": 99, "status": "ready"},
        }
        monkeypatch.setattr(instruction.db, "get_aia_source", lambda u: zeilen.get(u))
        assert instruction._ready_ids(42, ["fertig", "laeuft", "fremd", "weg"]) == [1]
