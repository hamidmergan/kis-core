"""Die pruefbaren Teile des Fragen-Bauers fuer den breiten Messsatz.

Der Bauer zieht Chunks aus einem Workspace, laesst ein Modell je eine Frage
dazu schreiben und legt beides als Messfall ab. Modellaufruf und Datenbank sind
hier aussen vor, geprueft wird was auch ohne beides falsch sein kann:

* welche Chunks ueberhaupt taugen (ein Ueberschriften-Chunk traegt keine Antwort)
* welcher Textausschnitt als Beleg dient (er muss woertlich wiederfindbar sein)
* was von der Antwort des Modells uebrig bleibt (Modelle liefern Zierrat)
"""
import pytest

from scripts.build_retrieval_cases import (
    _beleg, _frage_saeubern, _pruefe_schreibbar, _taugt_als_quelle,
)


LANG = (
    "Die Ruhezeit nach Beendigung der taeglichen Arbeitszeit betraegt mindestens elf "
    "Stunden ununterbrochen. Abweichend davon koennen in Krankenhaeusern und anderen "
    "Einrichtungen zur Behandlung von Personen die Ruhezeiten um bis zu eine Stunde "
    "verkuerzt werden, wenn jede Verkuerzung innerhalb eines Kalendermonats ausgeglichen "
    "wird. Der Ausgleich muss durch Verlaengerung einer anderen Ruhezeit erfolgen."
)


# ── Welche Chunks taugen ──────────────────────────────────────────────────────

def test_langer_fliesstext_taugt():
    assert _taugt_als_quelle(LANG) is True


def test_ueberschrift_taugt_nicht():
    # Rund ein Drittel der Chunks im Bestand sind Kopfzeilen dieser Art. Eine Frage
    # dazu waere unbeantwortbar und der Messsatz damit stiller Unsinn.
    assert _taugt_als_quelle("§ 5 Ruhezeit") is False
    assert _taugt_als_quelle("Inhaltsuebersicht") is False


def test_leeres_oder_fehlendes_taugt_nicht():
    assert _taugt_als_quelle("") is False
    assert _taugt_als_quelle(None) is False


def test_kurzer_absatz_taugt_nicht():
    # Zu kurz, um eine Frage zu tragen, die nicht der halbe Text selbst ist.
    assert _taugt_als_quelle("Die Ruhezeit betraegt elf Stunden.") is False


# ── Der Beleg ─────────────────────────────────────────────────────────────────

def test_beleg_steht_woertlich_im_text():
    # Der Messsatz sucht den Beleg spaeter per ILIKE. Steht er nicht woertlich drin,
    # ist der Fall von Anfang an unmessbar.
    b = _beleg(LANG)
    assert b and b in " ".join(LANG.split())


def test_beleg_faellt_nicht_mit_dem_anfang_zusammen():
    # Der Anfang eines Chunks ist oft die Ueberschrift oder der Paragrafenkopf und
    # taucht wortgleich in vielen Chunks auf. Ein Beleg von dort waere mehrdeutig.
    assert not " ".join(LANG.split()).startswith(_beleg(LANG))


def test_beleg_beginnt_und_endet_auf_ganzen_woertern():
    b = _beleg(LANG)
    assert not b.startswith(" ") and not b.endswith(" ")
    worte = " ".join(LANG.split()).split(" ")
    assert b.split(" ")[0] in worte
    assert b.split(" ")[-1] in worte


def test_beleg_glaettet_zeilenumbrueche():
    # Im PDF-Text steht der Umbruch mitten im Satz. Der Messsatz normalisiert beim
    # Suchen ebenso, beides muss zueinander passen.
    roh = LANG.replace(" ", "\n", 1).replace("Stunden ", "Stunden\n   ", 1)
    assert "\n" not in _beleg(roh)


def test_kein_beleg_aus_zu_kurzem_text():
    assert _beleg("Zu kurz fuer einen tragfaehigen Beleg.") is None


def test_belegLaenge_ist_einstellbar():
    assert len(_beleg(LANG, laenge=30)) <= 30
    assert len(_beleg(LANG, laenge=80)) <= 80


# ── Die Antwort des Modells ───────────────────────────────────────────────────

def test_anfuehrungszeichen_fallen_weg():
    assert _frage_saeubern('"Wie lang ist die Ruhezeit?"') == "Wie lang ist die Ruhezeit?"
    assert _frage_saeubern("„Wie lang ist die Ruhezeit?“") == "Wie lang ist die Ruhezeit?"


def test_vorangestelltes_etikett_faellt_weg():
    assert _frage_saeubern("Frage: Wie lang ist die Ruhezeit?") == "Wie lang ist die Ruhezeit?"
    assert _frage_saeubern("Question: Wie lang ist die Ruhezeit?") == "Wie lang ist die Ruhezeit?"


def test_nur_die_erste_zeile_zaehlt():
    roh = "Wie lang ist die Ruhezeit?\nHier noch eine Erlaeuterung dazu."
    assert _frage_saeubern(roh) == "Wie lang ist die Ruhezeit?"


def test_ohne_fragezeichen_verworfen():
    # Modelle liefern gelegentlich eine Aussage statt einer Frage. Die waere als
    # Suchanfrage untypisch und wuerde die Messung schoenen.
    assert _frage_saeubern("Die Ruhezeit betraegt elf Stunden.") is None


def test_leeres_verworfen():
    assert _frage_saeubern("") is None
    assert _frage_saeubern("   ") is None
    assert _frage_saeubern(None) is None


def test_ausschweifendes_verworfen():
    # Eine halbe Seite ist keine Nutzerfrage. Die Schranke haelt den Satz realistisch.
    assert _frage_saeubern("Wie " + "lang " * 80 + "ist die Ruhezeit?") is None


@pytest.mark.parametrize("roh", ["```\nWie lang ist die Ruhezeit?\n```",
                                 "```text\nWie lang ist die Ruhezeit?\n```"])
def test_codezaun_faellt_weg(roh):
    assert _frage_saeubern(roh) == "Wie lang ist die Ruhezeit?"


# ── Der Schreibweg ────────────────────────────────────────────────────────────

def test_schreibbarer_pfad_wird_angenommen(tmp_path):
    _pruefe_schreibbar(tmp_path / "neu.json")     # legt nichts an, wirft nur nicht


def test_fehlendes_verzeichnis_faellt_auf(tmp_path):
    with pytest.raises(SystemExit):
        _pruefe_schreibbar(tmp_path / "gibtsnicht" / "neu.json")


def test_verzeichnis_statt_datei_faellt_auf(tmp_path):
    ziel = tmp_path / "isteinordner"
    ziel.mkdir()
    with pytest.raises(SystemExit):
        _pruefe_schreibbar(ziel)


def test_bestehende_datei_bleibt_unveraendert(tmp_path):
    # Die Pruefung darf den vorherigen Satz nicht anfassen: wer den Lauf abbricht,
    # soll seine alte Datei unversehrt wiederfinden.
    ziel = tmp_path / "alt.json"
    ziel.write_text('[{"id": "alt"}]', encoding="utf-8")
    _pruefe_schreibbar(ziel)
    assert ziel.read_text(encoding="utf-8") == '[{"id": "alt"}]'


def test_probeschreiben_hinterlaesst_nichts(tmp_path):
    ziel = tmp_path / "neu.json"
    _pruefe_schreibbar(ziel)
    assert not ziel.exists()
