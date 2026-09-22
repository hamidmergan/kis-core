"""Prüft das Lesen einer Quelle: Seiten zusammensetzen, Stücke schneiden, Fundstellen."""

import pytest

from src.services.source_reading import (
    NoReadableText,
    Piece,
    Source,
    _assemble,
    _pieces,
    _seite_von,
    from_dict,
    read_file,
)


# ── Seiten zusammensetzen ────────────────────────────────────────────────────

def test_eine_seite_ist_der_ganze_text():
    text, grenzen = _assemble(["Hallo Welt"])
    assert text == "Hallo Welt"
    assert grenzen == [(1, 0, 10)]


def test_zwei_seiten_haengen_mit_leerzeile_aneinander():
    text, grenzen = _assemble(["AAA", "BBB"])
    assert text == "AAA\n\nBBB"
    assert grenzen == [(1, 0, 3), (2, 5, 8)]


def test_eine_leere_seite_nimmt_keinen_platz_aber_die_nummern_stimmen_weiter():
    text, grenzen = _assemble(["AAA", "", "CCC"])
    assert text == "AAA\n\nCCC"
    assert grenzen == [(1, 0, 3), (3, 5, 8)]


def test_ohne_seiten_bleibt_alles_leer():
    assert _assemble([]) == ("", [])


def test_nur_leere_seiten_geben_leeren_text():
    assert _assemble(["", "  "]) == ("", [])


# ── Seite einer Stelle ───────────────────────────────────────────────────────

def test_die_stelle_findet_ihre_seite():
    grenzen = [(1, 0, 10), (2, 12, 20)]
    assert _seite_von(0, grenzen) == 1
    assert _seite_von(9, grenzen) == 1
    assert _seite_von(12, grenzen) == 2
    assert _seite_von(19, grenzen) == 2


def test_eine_stelle_im_seitenumbruch_gehoert_zur_letzten_seite():
    """Zwischen zwei Seiten steht die Leerzeile, die gehoert keiner Seite."""
    grenzen = [(1, 0, 10), (2, 12, 20)]
    assert _seite_von(11, grenzen) == 2


def test_ohne_grenzen_gilt_seite_eins():
    assert _seite_von(5, []) == 1


# ── Stücke ───────────────────────────────────────────────────────────────────

def test_stuecke_decken_den_ganzen_text_ohne_luecke():
    text, grenzen = _assemble([("wort " * 400).strip()])
    stuecke = _pieces(text, grenzen)
    assert stuecke[0].von == 0
    assert stuecke[-1].bis == len(text)
    assert all(b.von <= a.bis for a, b in zip(stuecke, stuecke[1:]))


def test_jedes_stueck_traegt_eine_seite():
    text, grenzen = _assemble(["wort " * 300, "satz " * 300])
    stuecke = _pieces(text, grenzen)
    assert {s.seite for s in stuecke} == {1, 2}
    assert all(a.seite <= b.seite for a, b in zip(stuecke, stuecke[1:]))


def test_ein_kurzer_text_ist_ein_einziges_stueck():
    text, grenzen = _assemble(["kurz"])
    assert _pieces(text, grenzen) == [Piece(seite=1, von=0, bis=4)]


# ── Hin und zurück durch den Auftragsordner ──────────────────────────────────

def test_eine_quelle_kommt_unveraendert_zurueck():
    quelle = Source(dateiname="a.pdf", fassung="abc", text="Hallo",
                    stuecke=[Piece(seite=1, von=0, bis=5)], seiten=1)
    assert from_dict(quelle.as_dict()) == quelle


def test_eine_beschaedigte_quelle_wird_nicht_zum_absturz():
    assert from_dict({}) == Source(dateiname="", fassung="", text="", stuecke=[], seiten=0)


# ── Ganze Datei ──────────────────────────────────────────────────────────────

def test_eine_textdatei_wird_gelesen_und_bekommt_ihre_pruefsumme(tmp_path):
    datei = tmp_path / "notiz.txt"
    datei.write_text("Ein Satz mit Inhalt.", encoding="utf-8")
    quelle = read_file(str(datei), "notiz.txt")
    assert quelle.text == "Ein Satz mit Inhalt."
    assert quelle.seiten == 1
    assert len(quelle.fassung) == 64
    assert quelle.stuecke == [Piece(seite=1, von=0, bis=20)]


def test_dieselbe_datei_gibt_dieselbe_pruefsumme(tmp_path):
    a, b = tmp_path / "a.txt", tmp_path / "b.txt"
    a.write_text("gleich", encoding="utf-8")
    b.write_text("gleich", encoding="utf-8")
    assert read_file(str(a), "a.txt").fassung == read_file(str(b), "b.txt").fassung


def test_eine_geaenderte_datei_gibt_eine_andere_pruefsumme(tmp_path):
    datei = tmp_path / "a.txt"
    datei.write_text("vorher", encoding="utf-8")
    vorher = read_file(str(datei), "a.txt").fassung
    datei.write_text("nachher", encoding="utf-8")
    assert read_file(str(datei), "a.txt").fassung != vorher


def test_eine_leere_datei_wird_abgelehnt(tmp_path):
    datei = tmp_path / "leer.txt"
    datei.write_text("   \n  ", encoding="utf-8")
    with pytest.raises(NoReadableText):
        read_file(str(datei), "leer.txt")


def test_ein_unbekanntes_format_wird_abgelehnt(tmp_path):
    datei = tmp_path / "bild.png"
    datei.write_bytes(b"\x89PNG")
    with pytest.raises(ValueError):
        read_file(str(datei), "bild.png")
