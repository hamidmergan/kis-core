"""Eintraege ohne Datum duerfen nicht in einen Topf fallen.

Beim Zusammenfuehren schuetzt normalerweise das Datum: zwei Eintraege kommen nur
zusammen, wenn sie am selben Tag liegen. Alle offenen Termine teilen sich aber dasselbe
leere Datum, damit entscheidet dort allein der Titelvergleich.

Der bisherige Vergleich zaehlt Wortueberdeckung mit Wortstamm ab fuenf Zeichen. Bei
zweiwortigen Titeln reicht das nicht: "Praesentation: online" und "Online-Praesenz:
Peer-Review" kamen auf volle Uebereinstimmung, weil "online" woertlich trifft und
"praesentation" ueber den Stamm auf "praesenz" faellt. Im echten Lauf wanderte der
richtige offene Termin dadurch in einen falschen Eintrag, samt seiner Quellenangabe.

Die Titel unten stammen aus genau diesem Lauf.
"""

from datetime import date

import pytest

from src.features.ai_assistant.tasks.studio.schedule._titles import (
    _find_merge_target,
    _fuzzy_same,
    _fuzzy_same_undated,
    _same_source_text,
)


@pytest.mark.parametrize("a,b", [
    ("Präsentation: online", "Online-Präsenz: Peer-Review"),
    ("Präsentation: online", "Online-Präsenz: Schreibwerkstatt, Poster"),
    ("Präsentationen: online", "Online-Präsenz: Peer-Review"),
    ("Präsentation", "Online-Präsenz: Peer-Review"),
    ("Sprechstunde nach Absprache", "Online-Präsenz: Peer-Review"),
])
def test_verschiedene_offene_termine_bleiben_getrennt(a, b):
    assert _fuzzy_same_undated(a, b) is False


@pytest.mark.parametrize("a,b", [
    ("Präsentation", "Präsentation: online"),
    ("Präsentationen: online", "Präsentation: online"),
    ("Präsentationstermine", "Präsentationstermin"),
])
def test_derselbe_offene_termin_kommt_weiterhin_zusammen(a, b):
    assert _fuzzy_same_undated(a, b) is True


def test_der_alte_vergleich_haette_sie_zusammengeworfen():
    """Der Nachweis, dass die Verschaerfung noetig war und nicht nur Kosmetik ist."""
    assert _fuzzy_same("Präsentation: online", "Online-Präsenz: Peer-Review") is True


def test_leere_titel_kommen_nie_zusammen():
    assert _fuzzy_same_undated("", "Online-Präsenz: Peer-Review") is False
    assert _fuzzy_same_undated("Präsentation", "") is False


# --- der Wortlaut schlaegt den Titel -----------------------------------------
#
# Derselbe Kursplan steht in mehreren PDFs des Semesters. Das Modell nannte dieselbe
# Zeile im Lauf vom 13.08. einmal "Präsentation: Hausarbeit" und einmal
# "Präsentationen: online" und legte sie in zwei Gruppen, obwohl beide Fundstellen Wort
# für Wort derselbe Satz sind. Titel sind Auslegung, der Wortlaut ist nachprüfbar.

ZEILE = ("Präsentationen (online)                                    "
         "| während der Prüfungswochen (wird individuell vereinbart) |          |")


def test_gleicher_wortlaut_findet_den_eintrag():
    refs = [{"raw_quote": ZEILE, "page_number": 6}]
    assert _same_source_text(ZEILE, refs) is True


def test_abstand_und_grossschreibung_stoeren_nicht():
    """Dieselbe Tabellenzeile kommt aus zwei PDFs mit anderer Spaltenbreite."""
    anders = "  präsentationen (online) | während der Prüfungswochen (wird individuell vereinbart) |   |  "
    assert _same_source_text(anders, [{"raw_quote": ZEILE}]) is True


def test_anderer_wortlaut_findet_nichts():
    anders = "Präsentation. Die werden dann später individuell vereinbart."
    assert _same_source_text(anders, [{"raw_quote": ZEILE}]) is False


def test_leerer_wortlaut_findet_nichts():
    assert _same_source_text("", [{"raw_quote": ZEILE}]) is False
    assert _same_source_text(ZEILE, [{"raw_quote": ""}]) is False


def test_eine_von_mehreren_fundstellen_reicht():
    refs = [{"raw_quote": "irgendwas anderes"}, {"raw_quote": ZEILE}]
    assert _same_source_text(ZEILE, refs) is True


# --- die Entscheidung, in welchen Eintrag ein Fund gehoert -------------------

def _eintrag(id_, due_date, title, quote):
    return {"id": id_, "due_date": due_date, "title": title,
            "source_refs": [{"raw_quote": quote, "page_number": 4}]}


def test_gleicher_satz_landet_im_selben_eintrag_trotz_anderem_titel():
    """Der Fall aus dem Lauf vom 13.08.: das Modell nannte dieselbe Tabellenzeile
    einmal "Präsentation: Hausarbeit" und einmal "Präsentationen: online"."""
    vorhanden = [_eintrag(1, None, "Präsentation: Hausarbeit", ZEILE)]

    ziel = _find_merge_target(vorhanden, None, "day", "Präsentationen: online",
                              {"raw_quote": ZEILE, "page_number": 6})

    assert ziel is not None and ziel["id"] == 1


def test_anderer_satz_und_anderer_titel_ergeben_einen_neuen_eintrag():
    vorhanden = [_eintrag(1, None, "Präsentation: Hausarbeit", ZEILE)]

    ziel = _find_merge_target(vorhanden, None, "day", "Sprechstunde nach Absprache",
                              {"raw_quote": "Sprechstunde nach Absprache im Büro"})

    assert ziel is None


def test_aehnlicher_titel_reicht_weiterhin():
    vorhanden = [_eintrag(1, None, "Präsentationen: online", ZEILE)]

    ziel = _find_merge_target(vorhanden, None, "day", "Präsentation: online",
                              {"raw_quote": "ganz anderer Satz"})

    assert ziel is not None and ziel["id"] == 1


def test_mit_datum_zaehlt_der_wortlaut_nicht():
    """Mit Datum bindet der Tag, der Titelvergleich bleibt der alte. Sonst wuerde eine
    wiederholte Tabellenzeile Termine ueber verschiedene Tage hinweg zusammenziehen."""
    tag = date(2026, 5, 29)
    vorhanden = [_eintrag(1, tag, "Online-Präsenz: Peer-Review", ZEILE)]

    ziel = _find_merge_target(vorhanden, tag, "day", "Klausur Statistik",
                              {"raw_quote": ZEILE})

    assert ziel is None


def test_ein_anderer_tag_wird_nie_zusammengelegt():
    vorhanden = [_eintrag(1, date(2026, 5, 29), "Online-Präsenz: Peer-Review", ZEILE)]

    ziel = _find_merge_target(vorhanden, date(2026, 6, 27), "day",
                              "Online-Präsenz: Peer-Review", {"raw_quote": ZEILE})

    assert ziel is None
