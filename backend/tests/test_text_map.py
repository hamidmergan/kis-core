"""Prüft die Textkarte: Nummern, Teile je Fenster, gültige Stellen, Passagen, Themen."""

import json

import pytest

from src.limits import MAP_MAX_REFS, MAP_RANGE_MAX
from src.services import text_map as tm
from src.services.source_reading import Piece, Source


def _quelle(name: str, stuecke: int, *, laenge: int = 10, ueberlappung: int = 0,
            je_seite: int = 1) -> Source:
    """Eine Quelle aus gleich langen Stuecken, auf Wunsch ueberlappend wie beim Lesen."""
    schritt = laenge - ueberlappung
    text = "".join(chr(65 + i % 26) * schritt for i in range(stuecke)) + "z" * ueberlappung
    teile = [Piece(seite=1 + i // je_seite, von=i * schritt, bis=i * schritt + laenge)
             for i in range(stuecke)]
    return Source(dateiname=name, fassung="x", text=text, seiten=teile[-1].seite, stuecke=teile)


# ── Nummern ──────────────────────────────────────────────────────────────────

def test_die_nummern_laufen_ueber_alle_quellen_ab_eins():
    karte = tm.Karte([_quelle("a.pdf", 2), _quelle("b.pdf", 3)])
    assert len(karte) == 5
    assert karte.stelle(1) == tm.Stelle(source=0, piece=0)
    assert karte.stelle(3) == tm.Stelle(source=1, piece=0)


def test_eine_nummer_zeigt_ihr_stueck_nur_bis_zum_naechsten():
    """Ueberlappende Stuecke wuerden den Text auf der Karte sonst doppeln."""
    karte = tm.Karte([_quelle("a.pdf", 3, laenge=10, ueberlappung=4)])
    assert karte.segment(1) == "A" * 6
    assert karte.segment(3) == "C" * 6 + "zzzz"


def test_der_block_nennt_jede_datei_einmal_vor_ihren_stellen():
    block = tm.Karte([_quelle("a.pdf", 2), _quelle("b.pdf", 1)]).block()
    assert block.split("\n\n") == [
        "=== a.pdf ===", "[1] " + "A" * 10, "[2] " + "B" * 10,
        "=== b.pdf ===", "[3] " + "A" * 10]


# ── Teile je Fenster ─────────────────────────────────────────────────────────

def test_was_ins_fenster_passt_bleibt_ein_teil():
    karte = tm.Karte([_quelle("a.pdf", 50)])
    assert karte.teile(262_144) == [range(1, 51)]


def test_ein_zu_kleines_fenster_wird_abgelehnt():
    with pytest.raises(tm.WindowTooSmall):
        tm.Karte([_quelle("a.pdf", 5)]).teile(20_000)


def test_ein_unvermessenes_modell_rechnet_mit_dem_kleinsten_fenster():
    assert tm.window_chars(0) == tm.window_chars(131_072)


def test_zu_viel_text_wird_in_teile_ohne_luecke_geschnitten(monkeypatch):
    monkeypatch.setattr(tm, "window_chars", lambda fenster: 1_000)
    karte = tm.Karte([_quelle("a.pdf", 200, je_seite=4)])
    teile = karte.teile(262_144)
    assert len(teile) >= 2
    assert teile[0].start == 1 and teile[-1].stop == 201
    assert all(a.stop == b.start for a, b in zip(teile, teile[1:]))


def test_geschnitten_wird_an_einem_seitenwechsel(monkeypatch):
    monkeypatch.setattr(tm, "window_chars", lambda fenster: 1_000)
    karte = tm.Karte([_quelle("a.pdf", 200, je_seite=4)])
    for teil in karte.teile(262_144)[1:]:
        # The first number of a part starts a new page.
        assert (teil.start - 1) % 4 == 0


# ── Gültige Stellen ──────────────────────────────────────────────────────────

def test_zahlen_und_bereiche_werden_gelesen():
    karte = tm.Karte([_quelle("a.pdf", 20)])
    assert karte.gueltig([3, "5-7", "9–10", "12"]) == [3, 5, 6, 7, 9, 10, 12]


def test_erfundene_doppelte_und_unsinnige_nummern_fallen_weg():
    karte = tm.Karte([_quelle("a.pdf", 5)])
    assert karte.gueltig([0, 2, 2, 99, "x", True, None, "4"]) == [2, 4]


def test_ein_bereich_ist_gedeckelt():
    karte = tm.Karte([_quelle("a.pdf", 500)])
    assert len(karte.gueltig(["1-400"])) == MAP_RANGE_MAX


def test_ein_eintrag_ist_gedeckelt():
    karte = tm.Karte([_quelle("a.pdf", 500)])
    assert len(karte.gueltig([f"{i * 20 + 1}-{i * 20 + 20}" for i in range(10)])) == MAP_MAX_REFS


def test_keine_liste_gibt_keine_stellen():
    assert tm.Karte([_quelle("a.pdf", 5)]).gueltig("3") == []


# ── Passagen ─────────────────────────────────────────────────────────────────

def test_eine_stelle_bringt_ihre_nachbarn_mit():
    karte = tm.Karte([_quelle("a.pdf", 10)])
    passage = karte.passagen([5], nachbarn=1)
    assert "D" * 10 + "E" * 10 + "F" * 10 in passage
    assert "C" not in passage.split("\n", 1)[1] and "G" not in passage


def test_nahe_stellen_werden_eine_passage():
    karte = tm.Karte([_quelle("a.pdf", 10)])
    assert karte.passagen([3, 5], nachbarn=1).count("[a.pdf, S.") == 1


def test_ferne_stellen_bleiben_getrennt_mit_datei_und_seite():
    karte = tm.Karte([_quelle("a.pdf", 20, je_seite=5)])
    passage = karte.passagen([2, 18], nachbarn=0)
    assert passage.startswith("[a.pdf, S. 1]\n")
    assert "[a.pdf, S. 4]\n" in passage


def test_nachbarn_gehen_nie_ueber_die_quelle_hinaus():
    karte = tm.Karte([_quelle("a.pdf", 2), _quelle("b.pdf", 2)])
    passage = karte.passagen([2], nachbarn=1)
    assert "b.pdf" not in passage


def test_das_budget_schneidet_hinter_einer_ganzen_passage():
    karte = tm.Karte([_quelle("a.pdf", 30, je_seite=1)])
    passage = karte.passagen([1, 10, 20], nachbarn=0, budget=60)
    assert passage.count("[a.pdf") == 2


def test_die_ueberlappung_steht_in_der_passage_nur_einmal():
    karte = tm.Karte([_quelle("a.pdf", 3, laenge=10, ueberlappung=4)])
    text = karte.passagen([2], nachbarn=1).split("\n", 1)[1]
    assert text == karte.sources[0].text


# ── Themen, wenn der Text nicht passt ────────────────────────────────────────

def _themen_antwort(*titel_und_refs):
    return json.dumps({"topics": [{"title": t, "gist": f"{t} kurz", "refs": r}
                                  for t, r in titel_und_refs]})


def test_passt_der_text_wird_ueber_die_stellen_geplant():
    karte = tm.Karte([_quelle("a.pdf", 5)])
    gefragt = []
    g = tm.grundlage(karte, 262_144, language="German", zweck="x",
                     frage=lambda n: gefragt.append(n) or [])
    assert g.modus == tm.STELLEN and gefragt == []
    assert g.material == karte.block()


def test_passt_er_nicht_liest_jeder_teil_seine_themen(monkeypatch):
    monkeypatch.setattr(tm, "window_chars", lambda fenster: 1_000)
    karte = tm.Karte([_quelle("a.pdf", 200, je_seite=4)])
    gesendet = []

    def frage(nachrichten):
        gesendet.extend(nachrichten)
        return [_themen_antwort((f"T{i}", [str(i * 4 + 1)])) for i in range(len(nachrichten))]

    g = tm.grundlage(karte, 262_144, language="German", zweck="ein Podcast", frage=frage)
    assert g.modus == tm.THEMEN
    assert [t.nummer for t in g.themen] == list(range(1, len(gesendet) + 1))
    assert "part 1 of" in gesendet[0][0]["content"] and "ein Podcast" in gesendet[0][0]["content"]
    assert g.material.startswith("[1] T0: T0 kurz")


def test_themen_zeigen_zurueck_auf_ihre_stellen(monkeypatch):
    monkeypatch.setattr(tm, "window_chars", lambda fenster: 1_000)
    karte = tm.Karte([_quelle("a.pdf", 200)])
    g = tm.grundlage(karte, 262_144, language="German", zweck="x",
                     frage=lambda n: [_themen_antwort(("A", ["1-3"]), ("B", [7])), None]
                     + [None] * (len(n) - 2))
    assert g.stellen([2, 1, 2], karte) == [7, 1, 2, 3]


def test_ohne_ein_einziges_thema_scheitert_die_planung(monkeypatch):
    monkeypatch.setattr(tm, "window_chars", lambda fenster: 1_000)
    karte = tm.Karte([_quelle("a.pdf", 200)])
    with pytest.raises(RuntimeError):
        tm.grundlage(karte, 262_144, language="German", zweck="x",
                     frage=lambda n: ["kein json"] * len(n))


def test_ein_thema_ohne_gueltige_stelle_faellt_weg():
    karte = tm.Karte([_quelle("a.pdf", 5)])
    themen = tm.parse_themen(_themen_antwort(("A", [99]), ("B", ["2"])), karte, 1)
    assert [(t.nummer, t.titel, t.stellen) for t in themen] == [(1, "B", (2,))]


def test_die_grundlage_ueberlebt_den_auftragsordner():
    karte = tm.Karte([_quelle("a.pdf", 5)])
    g = tm.Grundlage(material="", modus=tm.THEMEN,
                     themen=[tm.Thema(nummer=1, titel="A", kern="k", stellen=(2, 3))])
    zurueck = tm.grundlage_aus_dict(json.loads(json.dumps(tm.grundlage_als_dict(g))), karte)
    assert zurueck.themen == g.themen and zurueck.material == "[1] A: k"
    stellen = tm.grundlage_aus_dict({"modus": "stellen", "themen": []}, karte)
    assert stellen.modus == tm.STELLEN and stellen.material == karte.block()


# ── Abdeckung ────────────────────────────────────────────────────────────────

def test_die_abdeckung_zaehlt_jede_stelle_einmal():
    assert tm.abdeckung([[1, 2], [2, 3]], 6) == 0.5


def test_ungenannte_stellen_gehen_an_den_naechsten_eintrag():
    assert tm.abdecken([[1, 2], [9, 10]], 10) == [[1, 2, 3, 4, 5], [6, 7, 8, 9, 10]]


def test_ein_eintrag_ohne_stellen_bleibt_leer():
    assert tm.abdecken([[], [3]], 4) == [[], [1, 2, 3, 4]]


def test_ohne_jede_stelle_bleibt_alles_wie_es_ist():
    assert tm.abdecken([[], []], 3) == [[], []]


def test_eine_datei_ohne_stelle_im_plan_fehlt():
    karte = tm.Karte([_quelle("a.pdf", 3), _quelle("b.pdf", 3)])
    assert tm.fehlende_dateien([[1, 2], []], karte) == ["b.pdf"]
    assert tm.fehlende_dateien([[1], [5]], karte) == []


def test_die_zielzahl_waechst_mit_dem_material_in_ihren_grenzen():
    assert tm.ziel_eintraege(60_000, 3, 30, grund=8, je=20_000) == 11
    assert tm.ziel_eintraege(364_000, 3, 30, grund=8, je=20_000) == 26
    assert tm.ziel_eintraege(5_000_000, 3, 30, grund=8, je=20_000) == 30


def test_eine_eingestreute_nummer_deckt_eine_grosse_datei_nicht_ab():
    """87 Prozent des Materials, im Plan nur eine von zwanzig Nummern: zu kurz."""
    karte = tm.Karte([_quelle("agg.pdf", 13), _quelle("amg.pdf", 87)])
    plan = [list(range(1, 11)), list(range(4, 13)) + [60]]
    assert tm.zu_kurz(plan, karte) == [("amg.pdf", 87)]


def test_ein_anteiliger_plan_ist_nicht_zu_kurz():
    karte = tm.Karte([_quelle("agg.pdf", 13), _quelle("amg.pdf", 87)])
    plan = [list(range(1, 9)), list(range(20, 40)), list(range(60, 75))]
    assert tm.zu_kurz(plan, karte) == []


def test_eine_winzige_datei_darf_fehlen():
    karte = tm.Karte([_quelle("gross.pdf", 97), _quelle("zettel.pdf", 3)])
    assert tm.zu_kurz([list(range(1, 50))], karte) == []
