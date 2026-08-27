"""Entries without a date need a stricter title comparison."""

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
    """The proof that the tightening was necessary and not just cosmetics."""
    assert _fuzzy_same("Präsentation: online", "Online-Präsenz: Peer-Review") is True


def test_leere_titel_kommen_nie_zusammen():
    assert _fuzzy_same_undated("", "Online-Präsenz: Peer-Review") is False
    assert _fuzzy_same_undated("Präsentation", "") is False


# Titles are interpretation, the wording is verifiable and beats them.

ZEILE = ("Präsentationen (online)                                    "
         "| während der Prüfungswochen (wird individuell vereinbart) |          |")


def test_gleicher_wortlaut_findet_den_eintrag():
    refs = [{"raw_quote": ZEILE, "page_number": 6}]
    assert _same_source_text(ZEILE, refs) is True


def test_abstand_und_grossschreibung_stoeren_nicht():
    """The same table row comes from two PDFs with different column widths."""
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


# --- the decision which entry a finding belongs to ---------------------------

def _eintrag(id_, due_date, title, quote):
    return {"id": id_, "due_date": due_date, "title": title,
            "source_refs": [{"raw_quote": quote, "page_number": 4}]}


def test_gleicher_satz_landet_im_selben_eintrag_trotz_anderem_titel():
    """The model gave the same table row two different titles."""
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
    """With a date the day binds, there the old comparison stays."""
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
