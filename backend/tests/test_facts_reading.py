"""Prüft die Lesephase: Stückgröße am Fenster, Schnitt an der Seite, Nebenläufigkeit."""

import asyncio

import pytest

from src.limits import FACTS_SLICE_MAX_CHARS
from src.services.facts_reading import (
    RateLimited,
    RunInterrupted,
    Slice,
    WindowTooSmall,
    by_source,
    map_slices,
    overloaded,
    plan_slices,
    slice_chars,
)
from src.services.source_reading import Piece, Source


def _quelle(zeichen: int, stueckgroesse: int = 1000, seiten_je: int = 5) -> Source:
    stuecke = [Piece(seite=1 + i // seiten_je, von=i * stueckgroesse,
                     bis=min((i + 1) * stueckgroesse, zeichen))
               for i in range(-(-zeichen // stueckgroesse))]
    return Source(dateiname="a.pdf", fassung="x", text="x" * zeichen,
                  stuecke=stuecke, seiten=stuecke[-1].seite if stuecke else 0)


class _Store:
    def __init__(self, vorhanden=None):
        self.gespeichert: dict[str, tuple[list, bool]] = {}
        self.vorhanden = vorhanden or {}
        self.fortschritt: list[tuple] = []

    def load_slices(self):
        return dict(self.vorhanden)

    def save_slice(self, key, facts, vollstaendig):
        self.gespeichert[key] = (facts, vollstaendig)

    def progress(self, step, part=None, total=None):
        self.fortschritt.append((step, part, total))

    def heartbeat(self):
        pass


# ── Stückgröße am Fenster ────────────────────────────────────────────────────

def test_ein_grosses_fenster_wird_vom_deckel_begrenzt():
    """Auf 262k passte mehr, geteilt wird trotzdem wegen der Ausgabe."""
    assert slice_chars(262_144) == FACTS_SLICE_MAX_CHARS


def test_ein_kleines_fenster_begrenzt_die_stuecke():
    # (65.536 - 16.000 - 3.000) * 3
    assert slice_chars(65_536) == 139_608


def test_ein_unvermessenes_modell_bekommt_den_deckel():
    assert slice_chars(0) == FACTS_SLICE_MAX_CHARS


def test_ein_zu_kleines_fenster_wird_abgelehnt():
    with pytest.raises(WindowTooSmall):
        slice_chars(20_080)


# ── Schnitt ──────────────────────────────────────────────────────────────────

def test_eine_kleine_datei_ist_ein_einziger_aufruf():
    teile = plan_slices([_quelle(50_000)], 250_000)
    assert len(teile) == 1
    assert teile[0] == Slice(source=0, von=0, bis=50, teil=1, teile=1)


def test_eine_grosse_datei_wird_geteilt():
    teile = plan_slices([_quelle(500_000)], 250_000)
    assert [t.teil for t in teile] == [1, 2]
    assert teile[0].von == 0 and teile[-1].bis == 500


def test_die_teile_decken_alle_stuecke_ohne_luecke():
    teile = plan_slices([_quelle(500_000)], 250_000)
    assert teile[0].bis == teile[1].von


def test_geschnitten_wird_an_einem_seitenwechsel():
    """Ein Stueck, dessen Seite sich von der des Vorgaengers unterscheidet."""
    quelle = _quelle(500_000, seiten_je=7)
    teile = plan_slices([quelle], 250_000)
    grenze = teile[1].von
    assert quelle.stuecke[grenze].seite != quelle.stuecke[grenze - 1].seite


def test_jede_quelle_bekommt_ihre_eigenen_teile():
    teile = plan_slices([_quelle(50_000), _quelle(500_000)], 250_000)
    assert [t.source for t in teile] == [0, 1, 1]


def test_eine_quelle_ohne_stuecke_faellt_weg():
    leer = Source(dateiname="leer.txt", fassung="x", text="", stuecke=[], seiten=0)
    assert plan_slices([leer], 250_000) == []


def test_mehr_teile_als_stuecke_gibt_es_nicht():
    teile = plan_slices([_quelle(3_000, stueckgroesse=1000)], 500)
    assert len(teile) <= 3


def test_die_stuecknummern_eines_teils_sind_sein_bereich():
    teil = Slice(source=0, von=10, bis=20, teil=2, teile=2)
    assert list(teil.pieces) == list(range(10, 20))
    assert teil.key == "0:2"


# ── Überlastung erkennen ─────────────────────────────────────────────────────

@pytest.mark.parametrize("status", [429, 503])
def test_abweisung_gilt_als_ueberlastung(status):
    fehler = Exception()
    fehler.status_code = status
    assert overloaded(fehler)


def test_eine_zeitueberschreitung_gilt_als_ueberlastung():
    assert overloaded(asyncio.TimeoutError())


def test_eine_schlechte_anfrage_gilt_nicht_als_ueberlastung():
    fehler = Exception()
    fehler.status_code = 400
    assert not overloaded(fehler)


# ── Lesephase ────────────────────────────────────────────────────────────────

def _lauf(teile, read, store, should_stop=None):
    return asyncio.run(map_slices(teile, read=read, store=store, should_stop=should_stop))


def test_jedes_stueck_wird_einmal_gelesen_und_gesichert():
    teile = plan_slices([_quelle(500_000)], 250_000)

    async def read(t):
        return [{"piece": t.von, "fact": f"Aus {t.key}"}], True

    store = _Store()
    aus = _lauf(teile, read, store)
    assert sorted(aus) == ["0:1", "0:2"]
    assert all(v[1] for v in store.gespeichert.values())


def test_ein_bereits_gelesenes_stueck_wird_nicht_erneut_gelesen():
    teile = plan_slices([_quelle(500_000)], 250_000)
    gelesen = []

    async def read(t):
        gelesen.append(t.key)
        return [], True

    store = _Store(vorhanden={"0:1": [{"fact": "alt"}]})
    aus = _lauf(teile, read, store)
    assert gelesen == ["0:2"]
    assert aus["0:1"] == [{"fact": "alt"}]


def test_ein_gescheitertes_stueck_wird_nicht_gespeichert():
    teile = plan_slices([_quelle(500_000)], 250_000)

    async def read(t):
        return None if t.teil == 1 else ([{"fact": "x"}], True)

    store = _Store()
    aus = _lauf(teile, read, store)
    assert "0:1" not in aus and "0:2" in aus


def test_eine_abgeschnittene_antwort_wird_als_unvollstaendig_gesichert():
    teile = plan_slices([_quelle(50_000)], 250_000)

    async def read(t):
        return [{"fact": "x"}], False

    store = _Store()
    _lauf(teile, read, store)
    assert store.gespeichert["0:1"][1] is False


def test_eine_abgewiesene_quelle_wird_mehrfach_versucht():
    teile = plan_slices([_quelle(50_000)], 250_000)
    versuche = []

    async def read(t):
        versuche.append(1)
        raise RateLimited("zu viel")

    store = _Store()
    _lauf(teile, read, store)
    assert len(versuche) == 3


def test_eine_abgelaufene_etappe_bricht_ab_und_behaelt_das_fertige():
    teile = plan_slices([_quelle(500_000)], 250_000)

    async def read(t):
        return [{"fact": "x"}], True

    store = _Store()
    with pytest.raises(RunInterrupted):
        _lauf(teile, read, store, should_stop=lambda: True)
    assert store.gespeichert == {}


def test_der_fortschritt_zaehlt_die_stuecke():
    teile = plan_slices([_quelle(500_000)], 250_000)

    async def read(t):
        return [], True

    store = _Store()
    _lauf(teile, read, store)
    assert store.fortschritt[0] == ("lesen", 0, 2)


# ── Zurück nach Quellen sortieren ────────────────────────────────────────────

def test_die_teile_einer_quelle_kommen_in_ihrer_reihenfolge_zurueck():
    teile = plan_slices([_quelle(500_000)], 250_000)
    gelesen = {"0:2": [{"fact": "zweiter"}], "0:1": [{"fact": "erster"}]}
    assert by_source(gelesen, teile, 1) == [[{"fact": "erster"}, {"fact": "zweiter"}]]


def test_jede_quelle_bekommt_ihren_eigenen_eintrag():
    teile = plan_slices([_quelle(50_000), _quelle(50_000)], 250_000)
    gelesen = {"0:1": [{"fact": "a"}], "1:1": [{"fact": "b"}]}
    assert by_source(gelesen, teile, 2) == [[{"fact": "a"}], [{"fact": "b"}]]


def test_eine_quelle_ohne_ergebnis_bleibt_leer():
    teile = plan_slices([_quelle(50_000), _quelle(50_000)], 250_000)
    assert by_source({"0:1": [{"fact": "a"}]}, teile, 2) == [[{"fact": "a"}], []]
