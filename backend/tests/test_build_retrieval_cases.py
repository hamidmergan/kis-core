"""Checks the parts of the question builder that can be wrong without a model."""
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
    # A question about a header line would be unanswerable.
    assert _taugt_als_quelle("§ 5 Ruhezeit") is False
    assert _taugt_als_quelle("Inhaltsuebersicht") is False


def test_leeres_oder_fehlendes_taugt_nicht():
    assert _taugt_als_quelle("") is False
    assert _taugt_als_quelle(None) is False


def test_kurzer_absatz_taugt_nicht():
    # Too short to carry a question that is not half the text itself.
    assert _taugt_als_quelle("Die Ruhezeit betraegt elf Stunden.") is False


# ── The evidence ──────────────────────────────────────────────────────────────

def test_beleg_steht_woertlich_im_text():
    # If the evidence is not there verbatim, the case cannot be measured.
    b = _beleg(LANG)
    assert b and b in " ".join(LANG.split())


def test_beleg_faellt_nicht_mit_dem_anfang_zusammen():
    # Evidence from the chunk start would be ambiguous.
    assert not " ".join(LANG.split()).startswith(_beleg(LANG))


def test_beleg_beginnt_und_endet_auf_ganzen_woertern():
    b = _beleg(LANG)
    assert not b.startswith(" ") and not b.endswith(" ")
    worte = " ".join(LANG.split()).split(" ")
    assert b.split(" ")[0] in worte
    assert b.split(" ")[-1] in worte


def test_beleg_glaettet_zeilenumbrueche():
    # Whitespace has to be flattened when building exactly as when searching.
    roh = LANG.replace(" ", "\n", 1).replace("Stunden ", "Stunden\n   ", 1)
    assert "\n" not in _beleg(roh)


def test_kein_beleg_aus_zu_kurzem_text():
    assert _beleg("Zu kurz fuer einen tragfaehigen Beleg.") is None


def test_belegLaenge_ist_einstellbar():
    assert len(_beleg(LANG, laenge=30)) <= 30
    assert len(_beleg(LANG, laenge=80)) <= 80


# ── The model's answer ────────────────────────────────────────────────────────

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
    # A statement instead of a question would flatter the measurement.
    assert _frage_saeubern("Die Ruhezeit betraegt elf Stunden.") is None


def test_leeres_verworfen():
    assert _frage_saeubern("") is None
    assert _frage_saeubern("   ") is None
    assert _frage_saeubern(None) is None


def test_ausschweifendes_verworfen():
    # Half a page is not a user question, the limit keeps it realistic.
    assert _frage_saeubern("Wie " + "lang " * 80 + "ist die Ruhezeit?") is None


@pytest.mark.parametrize("roh", ["```\nWie lang ist die Ruhezeit?\n```",
                                 "```text\nWie lang ist die Ruhezeit?\n```"])
def test_codezaun_faellt_weg(roh):
    assert _frage_saeubern(roh) == "Wie lang ist die Ruhezeit?"


# ── The write path ────────────────────────────────────────────────────────────

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
    # The check must not touch the previous set.
    ziel = tmp_path / "alt.json"
    ziel.write_text('[{"id": "alt"}]', encoding="utf-8")
    _pruefe_schreibbar(ziel)
    assert ziel.read_text(encoding="utf-8") == '[{"id": "alt"}]'


def test_probeschreiben_hinterlaesst_nichts(tmp_path):
    ziel = tmp_path / "neu.json"
    _pruefe_schreibbar(ziel)
    assert not ziel.exists()
