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


def _nah(monkeypatch, abstand=0.0):
    """Die Anweisung steckt im Material, die Abstandsmessung haelt nicht auf."""
    monkeypatch.setattr(instruction, "_probe", lambda ws, ids, anweisung: abstand)


def _budget(monkeypatch, chars=100_000):
    import src.features.ai_assistant.tasks._context_budget as budget
    monkeypatch.setattr(budget, "tool_context_budget", lambda: chars)


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
        _nah(monkeypatch)
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
        _nah(monkeypatch)
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
        _nah(monkeypatch)
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


class TestAbstand:
    """Eine Anweisung, zu der nichts im Material steht, darf keine Zufallsstellen ziehen."""

    @pytest.mark.asyncio
    async def test_anweisung_neben_dem_material_fuellt_auf(self, monkeypatch):
        _budget(monkeypatch)
        _vorcall(monkeypatch, instruction.SEARCH)
        _nah(monkeypatch, instruction.MAX_DIST + 0.05)
        monkeypatch.setattr(instruction, "_ready_ids", lambda ws, uuids: [7])
        gesucht = []
        monkeypatch.setattr(instruction, "_search", lambda *a: gesucht.append(a))
        notiz: dict = {}
        text = await instruction.build_context(
            _quellen(), "Sprich ueber Katzen und Hunde", 42, ["s1"], notiz)
        assert "Erster Abschnitt" in text and "Zweiter Abschnitt" in text
        assert gesucht == [], "liegt die Anweisung daneben, darf keine Suche starten"
        assert notiz["weg"] == instruction.FILL
        assert notiz["daneben"] is True

    @pytest.mark.asyncio
    async def test_anweisung_im_material_sucht_weiter(self, monkeypatch):
        _budget(monkeypatch)
        _vorcall(monkeypatch, instruction.SEARCH)
        _nah(monkeypatch, instruction.MAX_DIST - 0.05)
        monkeypatch.setattr(instruction, "_ready_ids", lambda ws, uuids: [7])

        async def _treffer(workspace_id, ids, anweisung):
            return [{"source_id": 7, "content": "Die Stelle zur Kuehlung"}]

        monkeypatch.setattr(instruction, "_search", _treffer)
        monkeypatch.setattr(instruction.db, "get_aia_source_by_id",
                            lambda sid: {"filename": "a.pdf"})
        notiz: dict = {}
        text = await instruction.build_context(_quellen(), "Kuehlung", 42, ["s1"], notiz)
        assert "Die Stelle zur Kuehlung" in text
        assert notiz["weg"] == instruction.SEARCH
        assert notiz.get("daneben") is None

    @pytest.mark.asyncio
    async def test_kaputte_messung_sucht_trotzdem(self, monkeypatch):
        _budget(monkeypatch)
        _vorcall(monkeypatch, instruction.SEARCH)
        monkeypatch.setattr(instruction, "_ready_ids", lambda ws, uuids: [7])

        def _kaputt(ws, ids, anweisung):
            raise RuntimeError("Einbettungsdienst weg")

        monkeypatch.setattr(instruction, "_probe", _kaputt)

        async def _treffer(workspace_id, ids, anweisung):
            return [{"source_id": 7, "content": "Die Stelle zur Kuehlung"}]

        monkeypatch.setattr(instruction, "_search", _treffer)
        monkeypatch.setattr(instruction.db, "get_aia_source_by_id",
                            lambda sid: {"filename": "a.pdf"})
        text = await instruction.build_context(_quellen(), "Kuehlung", 42, ["s1"])
        assert "Die Stelle zur Kuehlung" in text, "eine kaputte Messung darf nicht sperren"


class TestAbstandMessen:
    """Gemessen wird der Schnitt der besten Stellen, nicht die eine beste."""

    def _rows(self, *dists):
        return [{"vec_distance": d} for d in dists]

    def test_schnitt_der_besten_fuenf(self, monkeypatch):
        monkeypatch.setattr(instruction, "_embedder", lambda: (lambda t: [0.0]))
        monkeypatch.setattr(instruction.db, "hybrid_search_chunks",
                            lambda *a, **k: self._rows(0.1, 0.2, 0.3, 0.4, 0.5, 0.9, 0.9))
        assert instruction._probe(42, [7], "Kuehlung") == pytest.approx(0.3)

    def test_ohne_treffer_ist_der_abstand_hoechstens(self, monkeypatch):
        monkeypatch.setattr(instruction, "_embedder", lambda: (lambda t: [0.0]))
        monkeypatch.setattr(instruction.db, "hybrid_search_chunks", lambda *a, **k: [])
        assert instruction._probe(42, [7], "Kuehlung") == 1.0

    def test_stellen_ohne_abstand_zaehlen_nicht_mit(self, monkeypatch):
        monkeypatch.setattr(instruction, "_embedder", lambda: (lambda t: [0.0]))
        monkeypatch.setattr(instruction.db, "hybrid_search_chunks",
                            lambda *a, **k: [{"vec_distance": None}, {"vec_distance": 0.4}])
        assert instruction._probe(42, [7], "Kuehlung") == pytest.approx(0.4)
