"""Die Map-Phase des Fakten-Dienstes: ein Aufruf je Quelle, Bremse, Absagen, Etappenende."""

import asyncio

import pytest

from tests.facts_helpers import Abgewiesen, Leser, MemoryFactStore, fakten, quelle

from src.services.facts import Pacing, RateLimited, RunInterrupted, map_sources, overloaded


def _takt(**abweichend) -> Pacing:
    """Der Takt der Tests: keine Wartezeit, und nur ein Aufruf zugleich."""
    return Pacing(**{"concurrency": 1, "max_attempts": 3, "retry_delay": 0,
                     "max_backoff": 0, **abweichend})


async def _lauf(quellen, leser, speicher=None, takt=None, should_stop=None):
    speicher = speicher if speicher is not None else MemoryFactStore()
    ergebnis = await map_sources(quellen, read=leser, store=speicher,
                                 pacing=takt or _takt(), should_stop=should_stop)
    return ergebnis, speicher


class TestMapPhase:
    async def test_jede_quelle_wird_genau_einmal_gefragt(self):
        leser = Leser({f"doc_{i:02d}": [fakten("A")] for i in (1, 2, 3)})
        await _lauf([quelle(1), quelle(2), quelle(3)], leser)
        assert sorted(leser.gefragt) == ["doc_01", "doc_02", "doc_03"]

    async def test_die_fakten_landen_unter_ihrer_quelle(self):
        leser = Leser({"doc_01": [fakten("A")], "doc_02": [fakten("B")]})
        ergebnis, speicher = await _lauf([quelle(1), quelle(2)], leser)
        assert [f["fact"] for f in ergebnis["doc_01"]] == ["A"]
        assert [f["fact"] for f in speicher.extractions["doc_02"]] == ["B"]

    async def test_eine_bereits_gelesene_quelle_wird_uebersprungen(self):
        speicher = MemoryFactStore({"doc_01": fakten("alt")})
        leser = Leser({"doc_02": [fakten("B")]})
        ergebnis, _ = await _lauf([quelle(1), quelle(2)], leser, speicher)
        assert leser.gefragt == ["doc_02"]
        # Das Vorhandene steht weiter im Ergebnis, sonst faenge der Wiederanlauf von vorn an.
        assert [f["fact"] for f in ergebnis["doc_01"]] == ["alt"]

    async def test_ohne_offene_quelle_faellt_kein_aufruf_an(self):
        speicher = MemoryFactStore({"doc_01": fakten("alt")})
        leser = Leser({})
        ergebnis, _ = await _lauf([quelle(1)], leser, speicher)
        assert leser.gefragt == [] and list(ergebnis) == ["doc_01"]

    async def test_der_fortschritt_meldet_die_map_phase(self):
        leser = Leser({"doc_01": [fakten("A")]})
        _, speicher = await _lauf([quelle(1)], leser)
        assert ("map", None, None) in speicher.schritte

    async def test_eine_leere_antwort_wird_nicht_gespeichert(self):
        """Nichts gefunden ist kein Ergebnis, die naechste Etappe fragt noch einmal."""
        leser = Leser({"doc_01": [[]], "doc_02": [fakten("B")]})
        ergebnis, speicher = await _lauf([quelle(1), quelle(2)], leser)
        assert list(speicher.extractions) == ["doc_02"] and "doc_01" not in ergebnis

    async def test_ein_aufgegebener_lesevorgang_wird_nicht_gespeichert(self):
        leser = Leser({"doc_01": [None], "doc_02": [fakten("B")]})
        _, speicher = await _lauf([quelle(1), quelle(2)], leser)
        assert speicher.geschrieben == ["doc_02"]


class TestNebenlaeufigkeit:
    """Die Bremse ist der Schutz des Anbieters, gemessen 20.09. bei drei Aufrufen zugleich."""

    async def test_die_bremse_haelt_den_hoechststand(self):
        leser = Leser({f"doc_{i:02d}": [fakten("A")] for i in range(1, 8)})
        await _lauf([quelle(i) for i in range(1, 8)], leser, takt=_takt(concurrency=3))
        assert leser.hoechststand == 3

    async def test_bei_eins_laeuft_alles_nacheinander(self):
        leser = Leser({f"doc_{i:02d}": [fakten("A")] for i in range(1, 5)})
        await _lauf([quelle(i) for i in range(1, 5)], leser, takt=_takt(concurrency=1))
        assert leser.hoechststand == 1
        # Nacheinander heisst auch: in der Reihenfolge der Quellen.
        assert leser.gefragt == ["doc_01", "doc_02", "doc_03", "doc_04"]

    async def test_mehr_plaetze_als_quellen_bleibt_bei_den_quellen(self):
        leser = Leser({f"doc_{i:02d}": [fakten("A")] for i in (1, 2, 3)})
        await _lauf([quelle(i) for i in (1, 2, 3)], leser, takt=_takt(concurrency=10))
        assert leser.hoechststand == 3

    async def test_ohne_platz_laeuft_trotzdem_einer(self):
        """Eine Null im Adminbereich darf den Lauf nicht anhalten."""
        leser = Leser({"doc_01": [fakten("A")]})
        _, speicher = await _lauf([quelle(1)], leser, takt=_takt(concurrency=0))
        assert leser.hoechststand == 1 and list(speicher.extractions) == ["doc_01"]

    async def test_gespeichert_wird_ausserhalb_der_bremse(self):
        """Der naechste Aufruf startet, waehrend der vorige noch speichert."""
        laeuft = []

        class _Langsam(MemoryFactStore):
            def save_extraction(self, source_id, facts):
                laeuft.append(leser.gleichzeitig)
                super().save_extraction(source_id, facts)

        leser = Leser({f"doc_{i:02d}": [fakten("A")] for i in (1, 2, 3)})
        await _lauf([quelle(i) for i in (1, 2, 3)], leser, _Langsam(),
                    takt=_takt(concurrency=1))
        # Waehrend gespeichert wird, ist der Platz schon wieder von der naechsten Quelle belegt.
        assert max(laeuft) >= 1


class TestWiederholung:
    async def test_eine_absage_wird_wiederholt(self):
        leser = Leser({"doc_01": [RateLimited("429"), fakten("A")]})
        _, speicher = await _lauf([quelle(1)], leser)
        assert leser.gefragt == ["doc_01", "doc_01"]
        assert [f["fact"] for f in speicher.extractions["doc_01"]] == ["A"]

    async def test_die_wartezeit_waechst(self, monkeypatch):
        gewartet: list[float] = []
        echt = asyncio.sleep

        async def _merken(dauer, *rest):
            gewartet.append(dauer)
            await echt(0)

        monkeypatch.setattr(asyncio, "sleep", _merken)
        leser = Leser({"doc_01": [RateLimited("1"), RateLimited("2"), fakten("A")]}, dauer=0)
        await _lauf([quelle(1)], leser,
                    takt=_takt(retry_delay=3, max_backoff=60, max_attempts=3))
        assert [d for d in gewartet if d] == [3, 6]

    async def test_die_wartezeit_hat_eine_obergrenze(self, monkeypatch):
        gewartet: list[float] = []
        echt = asyncio.sleep

        async def _merken(dauer, *rest):
            gewartet.append(dauer)
            await echt(0)

        monkeypatch.setattr(asyncio, "sleep", _merken)
        leser = Leser({"doc_01": [RateLimited("1"), RateLimited("2"), fakten("A")]}, dauer=0)
        await _lauf([quelle(1)], leser,
                    takt=_takt(retry_delay=30, max_backoff=40, max_attempts=3))
        assert [d for d in gewartet if d] == [30, 40]

    async def test_eine_dauerhaft_abgewiesene_quelle_faellt_aus(self):
        leser = Leser({"doc_01": [RateLimited("429")] * 3})
        ergebnis, speicher = await _lauf([quelle(1)], leser)
        assert leser.gefragt == ["doc_01"] * 3
        assert ergebnis == {} and speicher.extractions == {}

    async def test_die_anderen_quellen_bleiben_davon_unberuehrt(self):
        leser = Leser({"doc_01": [RateLimited("429")] * 3, "doc_02": [fakten("B")]})
        _, speicher = await _lauf([quelle(1), quelle(2)], leser)
        assert list(speicher.extractions) == ["doc_02"]

    async def test_ein_versuch_heisst_keine_wiederholung(self):
        leser = Leser({"doc_01": [RateLimited("429"), fakten("A")]})
        _, speicher = await _lauf([quelle(1)], leser, takt=_takt(max_attempts=1))
        assert leser.gefragt == ["doc_01"] and speicher.extractions == {}

    async def test_ein_anderer_fehler_gehoert_dem_leser(self):
        """Nur eine Absage wird gestaffelt, alles andere raeumt der Leser selbst auf."""
        leser = Leser({"doc_01": [RuntimeError("kaputt")]})
        with pytest.raises(RuntimeError):
            await _lauf([quelle(1)], leser)


class TestEtappenende:
    async def test_die_uhr_bricht_den_lauf_ab(self):
        leser = Leser({f"doc_{i:02d}": [fakten("A")] for i in (1, 2, 3)})
        with pytest.raises(RunInterrupted):
            await _lauf([quelle(i) for i in (1, 2, 3)], leser, should_stop=lambda: True)

    async def test_was_fertig_ist_bleibt_gespeichert(self):
        gefragt = {"n": 0}

        def stop():
            gefragt["n"] += 1
            return gefragt["n"] > 1

        leser = Leser({f"doc_{i:02d}": [fakten("A")] for i in (1, 2, 3)})
        speicher = MemoryFactStore()
        with pytest.raises(RunInterrupted):
            await _lauf([quelle(i) for i in (1, 2, 3)], leser, speicher, should_stop=stop)
        assert list(speicher.extractions) == ["doc_01"]

    async def test_die_uhr_wird_erst_hinter_der_bremse_gefragt(self):
        """Vor der Bremse gefragt, entschiede jede Quelle beim Start und nicht an ihrer Reihe.

        Die Uhr laeuft ab, waehrend die erste Quelle gelesen wird. Wer vor dem Warten fragt,
        bekommt noch das alte Ja und liest weiter, obwohl die Etappe laengst vorbei ist.
        """
        start = asyncio.get_running_loop().time()

        def stop():
            return asyncio.get_running_loop().time() - start > 0.02

        leser = Leser({f"doc_{i:02d}": [fakten("A")] for i in (1, 2, 3)}, dauer=0.05)
        with pytest.raises(RunInterrupted):
            await _lauf([quelle(i) for i in (1, 2, 3)], leser, should_stop=stop,
                        takt=_takt(concurrency=1))
        assert leser.gefragt == ["doc_01"]

    async def test_ohne_uhr_laeuft_alles_durch(self):
        leser = Leser({f"doc_{i:02d}": [fakten("A")] for i in (1, 2, 3)})
        ergebnis, _ = await _lauf([quelle(i) for i in (1, 2, 3)], leser, should_stop=None)
        assert len(ergebnis) == 3


class TestUeberlastung:
    """Was als zu viel auf einmal gilt und was ein schlechter Aufruf ist."""

    def test_abweisung_und_ueberlastung_zaehlen(self):
        assert overloaded(Abgewiesen(429)) and overloaded(Abgewiesen(503))

    def test_eine_zeitueberschreitung_zaehlt(self):
        class _Zeit(Exception):
            pass

        _Zeit.__name__ = "APITimeoutError"
        assert overloaded(asyncio.TimeoutError()) and overloaded(_Zeit())

    def test_der_status_wird_auch_an_der_antwort_gefunden(self):
        fehler = Exception("weg")
        fehler.response = type("R", (), {"status_code": 429})()
        assert overloaded(fehler)

    def test_ein_schlechter_aufruf_zaehlt_nicht(self):
        assert not overloaded(Abgewiesen(400)) and not overloaded(RuntimeError("kaputt"))
