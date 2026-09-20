"""Fakten werden erst im Vorrat numeriert, darum ist die Nummer nach Wiederanlauf gleich."""

import json

from src.services.facts.pool import (
    Fact,
    build_pool,
    facts_block,
    facts_for,
    pool_block,
    parse_facts,
    source_names,
    unique_statements,
)

QUELLEN = [{"source_id": "doc_01", "filename": "a.pdf"},
           {"source_id": "doc_02", "filename": "b.pdf"}]


def _fakt(text: str) -> dict:
    return {"category": "figure", "fact": text, "citation": f"Beleg zu {text}"}


def test_nummern_folgen_den_dateien_nicht_der_antwortreihenfolge():
    """Die zweite Datei antwortet zuerst, numeriert wird trotzdem nach Dateireihenfolge."""
    gespeichert = {"doc_02": [_fakt("B")], "doc_01": [_fakt("A")]}
    vorrat = build_pool(QUELLEN, gespeichert)
    assert [f.fact_id for f in vorrat] == [1, 2]
    assert [f.fact for f in vorrat] == ["A", "B"]
    assert vorrat[0].source_name == "a.pdf"
    assert vorrat[1].source_id == "doc_02"


def test_der_vorrat_ist_nach_wiederanlauf_derselbe():
    gespeichert = {"doc_01": [_fakt("A"), _fakt("A2")], "doc_02": [_fakt("B")]}
    erst = build_pool(QUELLEN, gespeichert)
    nochmal = build_pool(QUELLEN, dict(reversed(list(gespeichert.items()))))
    assert [(f.fact_id, f.fact) for f in erst] == [(f.fact_id, f.fact) for f in nochmal]


def test_eine_datei_ohne_fakten_verschiebt_die_nummern_nicht():
    vorrat = build_pool(QUELLEN, {"doc_02": [_fakt("B")]})
    assert [(f.fact_id, f.source_name) for f in vorrat] == [(1, "b.pdf")]


def test_leere_aussagen_fallen_raus():
    vorrat = build_pool(QUELLEN, {"doc_01": [_fakt("A"), {"fact": "   "}]})
    assert [f.fact for f in vorrat] == ["A"]


def test_parse_nimmt_das_schema_objekt():
    fakten = parse_facts('{"facts": [{"category": "deadline", "fact": "x", "citation": "y"}]}')
    assert fakten == [{"category": "deadline", "fact": "x", "citation": "y", "reference": ""}]


def test_parse_nimmt_auch_ein_nacktes_array_und_einen_zaun():
    assert parse_facts('[{"fact": "x"}]')[0]["fact"] == "x"
    assert parse_facts('```json\n{"facts": [{"fact": "x"}]}\n```')[0]["fact"] == "x"
    assert parse_facts("<think>hm</think>\n{\"facts\": [{\"fact\": \"x\"}]}")[0]["fact"] == "x"


def test_parse_gibt_bei_muell_eine_leere_liste():
    assert parse_facts("das war nichts") == []
    assert parse_facts(None) == []
    assert parse_facts('{"facts": "kein array"}') == []


class TestWiederholungen:
    """Der Lese-Aufruf liefert denselben Satz je Kategorie einmal, der Leser sah ihn 4x."""

    _LANG = "Die zustaendige Behoerde hat innerhalb von sieben Monaten zu entscheiden"

    def test_gleicher_satz_bleibt_einmal(self):
        assert unique_statements(["Sieben Monate.", "Sieben Monate.", "Drei Monate."]) == [0, 2]

    def test_nur_die_zeichensetzung_unterscheidet_nicht(self):
        assert unique_statements(["Sieben Monate!", "sieben  monate."]) == [0]

    def test_die_vollere_fassung_gewinnt(self):
        knapp = self._LANG + "."
        voll = self._LANG + " nach Eingang des Antrags."
        assert unique_statements([knapp, voll]) == [1]

    def test_die_vollere_fassung_gewinnt_auch_umgekehrt(self):
        voll = self._LANG + " nach Eingang des Antrags."
        assert unique_statements([voll, self._LANG + "."]) == [0]

    def test_kurze_aussagen_werden_nicht_ineinander_geschoben(self):
        """'Drei Monate' steckt in 'Drei Monate nach Erhalt', ist aber zu kurz fuer den Schluss."""
        assert unique_statements(["Drei Monate.", "Drei Monate nach Erhalt."]) == [0, 1]

    def test_leere_aussagen_fallen_weg(self):
        assert unique_statements(["", "   ", "Etwas."]) == [2]

    def test_der_vorrat_numeriert_nach_der_entdopplung_durch(self):
        gespeichert = {"doc_01": [_fakt("A"), _fakt("A"), _fakt("B")]}
        vorrat = build_pool(QUELLEN, gespeichert)
        assert [(f.fact_id, f.fact) for f in vorrat] == [(1, "A"), (2, "B")]

    def test_entdoppelt_wird_auch_ueber_dateigrenzen_hinweg(self):
        gespeichert = {"doc_01": [_fakt("Gleiche Aussage.")],
                       "doc_02": [_fakt("Gleiche Aussage.")]}
        vorrat = build_pool(QUELLEN, gespeichert)
        assert [f.source_name for f in vorrat] == ["a.pdf"]


def test_der_vorrat_fuer_die_gliederung_traegt_nummer_und_datei_ohne_beleg():
    vorrat = build_pool(QUELLEN, {"doc_01": [_fakt("A")]})
    zeile = pool_block(vorrat, 10_000)
    assert zeile.startswith("#1 (figure) [a.pdf] A")
    assert "Beleg" not in zeile


def test_die_fakten_eines_abschnitts_tragen_ihren_beleg():
    vorrat = build_pool(QUELLEN, {"doc_01": [_fakt("A")]})
    assert 'Beleg: "Beleg zu A"' in facts_block(vorrat, 10_000)


class TestStelle:
    """Die Stelle ist ein eigenes Feld, weil sie als Prosa-Regel im Beleg versickerte."""

    def _mit_stelle(self, stelle: str) -> dict:
        return {"category": "figure", "fact": "A", "citation": "Beleg zu A",
                "reference": stelle}

    def test_die_stelle_steht_vor_dem_beleg(self):
        vorrat = build_pool(QUELLEN, {"doc_01": [self._mit_stelle("§ 27 Abs. 3")]})
        assert vorrat[0].reference == "§ 27 Abs. 3"
        assert 'Stelle: § 27 Abs. 3 Beleg: "Beleg zu A"' in facts_block(vorrat, 10_000)

    def test_ohne_stelle_steht_nur_der_beleg(self):
        vorrat = build_pool(QUELLEN, {"doc_01": [_fakt("A")]})
        assert "Stelle:" not in facts_block(vorrat, 10_000)

    def test_die_gliederung_sieht_die_stelle_nicht(self):
        vorrat = build_pool(QUELLEN, {"doc_01": [self._mit_stelle("§ 27")]})
        assert "Stelle:" not in pool_block(vorrat, 10_000)

    def test_eine_ausufernde_stelle_wird_gekuerzt(self):
        vorrat = build_pool(QUELLEN, {"doc_01": [self._mit_stelle("§ " + "1" * 200)]})
        assert len(vorrat[0].reference) == 80

    def test_ein_alter_auftrag_ohne_das_feld_laeuft_weiter(self):
        """facts.json aus einem Lauf vor dem Feld muss nach Wiederanlauf noch lesbar sein."""
        vorrat = build_pool(QUELLEN, {"doc_01": [{"category": "c", "fact": "A",
                                                  "citation": "b"}]})
        assert vorrat[0].reference == ""

    def test_die_stelle_kommt_aus_der_antwort(self):
        gelesen = parse_facts(json.dumps({"facts": [
            {"category": "figure", "fact": "A", "citation": "b", "reference": "§ 5"}]}))
        assert gelesen[0]["reference"] == "§ 5"


def test_der_vorrat_wird_auf_sein_budget_gekuerzt():
    vorrat = build_pool(QUELLEN, {"doc_01": [_fakt(f"Aussage {i} " + "x" * 500)
                                             for i in range(20)]})
    assert len(vorrat) == 20
    assert len(pool_block(vorrat, 1_000)) == 1_000


def test_unbekannte_nummern_fallen_beim_zuordnen_raus():
    vorrat = build_pool(QUELLEN, {"doc_01": [_fakt("A"), _fakt("A2")]})
    gewaehlt = facts_for([2, 99], vorrat)
    assert [f.fact for f in gewaehlt] == ["A2"]


def test_die_dateien_eines_abschnitts_werden_einmal_genannt():
    vorrat = [Fact(1, "c", "A", "", "doc_01", "a.pdf"), Fact(2, "c", "B", "", "doc_01", "a.pdf")]
    assert source_names(vorrat) == ["a.pdf"]


class TestAbgeschnitteneAntwort:
    """Der Token-Deckel darf nicht die ganze Datei kosten, fertige Fakten zaehlen."""

    ROH = ('{"facts": [{"category": "deadline", "fact": "A", "citation": "a"}, '
           '{"category": "figure", "fact": "B", "citation": "b"}, '
           '{"category": "figure", "fact": "C", "cit')

    def test_die_fertigen_fakten_werden_gerettet(self):
        fakten = parse_facts(self.ROH)
        assert [f["fact"] for f in fakten] == ["A", "B"]

    def test_eine_klammer_im_zitat_verwirrt_die_rettung_nicht(self):
        roh = ('[{"category": "c", "fact": "A", "citation": "er sagte } und {"}, '
               '{"category": "c", "fact": "B", "cit')
        assert [f["fact"] for f in parse_facts(roh)] == ["A"]

    def test_ein_geschuetztes_anfuehrungszeichen_bleibt_heil(self):
        roh = '[{"category": "c", "fact": "sagte \\"ja\\"", "citation": "a"}, {"fact": "B'
        assert parse_facts(roh)[0]["fact"] == 'sagte "ja"'

    def test_ohne_jede_fertige_klammer_bleibt_es_leer(self):
        assert parse_facts('{"facts": [{"category": "deadline", "fact": "A') == []
