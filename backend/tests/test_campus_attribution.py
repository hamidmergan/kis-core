"""Source cards follow the pages an answer drew on, not every fetched page."""
from src.features.campus.services.attribution import answer_units, used_sources

QUELLEN = [{"page_id": p, "title": f"Seite {p}"} for p in (1, 2, 3, 4, 5)]


def _nearest_from(table):
    """Each unit vector carries its index, the table maps it to page and distance."""
    return lambda vector, chunk_ids: table[int(vector[0])]


def _embed(units):
    return [[float(i)] for i in range(len(units))]


def test_einheiten_ohne_listenzeichen_und_bruchstuecke():
    text = "## Kosten\n\nDer Beitrag beträgt 394,30 €. Zahle ihn bald.\n* **Upload:** Personalausweis oder Reisepass\n1. 2026 beginnt das Semester im Oktober.\n- Ja"
    assert answer_units(text) == [
        "Der Beitrag beträgt 394,30 €.",
        "Zahle ihn bald.",
        "Upload: Personalausweis oder Reisepass",
        "2026 beginnt das Semester im Oktober.",
    ]


def test_eine_seite_ergibt_eine_karte():
    answer = "Der Semesterbeitrag beträgt 394,30 Euro. Er enthält das Semesterticket."
    out = used_sources(answer, QUELLEN, [10, 11], _embed, _nearest_from([(3, 0.3), (3, 0.4)]))
    assert out == [QUELLEN[2]]


def test_reihenfolge_der_antwort_und_ferne_saetze_zaehlen_nicht():
    answer = "Die Beratung sitzt im Raum A.1. Für alle Bachelorstudiengänge gilt. Sprechzeiten sind dienstags."
    out = used_sources(answer, QUELLEN, [10], _embed, _nearest_from([(4, 0.3), (1, 0.62), (2, 0.45)]))
    assert out == [QUELLEN[3], QUELLEN[1]]


def test_ohne_nahen_satz_keine_karte():
    answer = "Hallo! Wie kann ich dir heute helfen?"
    out = used_sources(answer, QUELLEN, [10], _embed, _nearest_from([(5, 0.7)]))
    assert out == []


def test_kaputte_einbettung_laesst_alle_fundstellen_stehen():
    def kaputt(units):
        raise RuntimeError("down")
    out = used_sources("Der Semesterbeitrag beträgt 394,30 Euro.", QUELLEN, [10], kaputt, _nearest_from([]))
    assert out == QUELLEN
