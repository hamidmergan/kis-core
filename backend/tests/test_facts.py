"""Prüft die Fakten: Auftragstext, Antwort lesen, Vorrat bauen, Rückweg in den Text."""

import json

from src.services.facts import (
    MAX_CATEGORY_CHARS,
    MAX_FACT_CHARS,
    Fact,
    build_pool,
    context_for,
    facts_for,
    from_dict,
    numbered_pieces,
    parse_answer,
    pool_block,
    salvage,
    system_prompt,
    unique_within,
)
from src.services.source_reading import Piece, Source


def _quelle(text: str, stuecke: list[tuple[int, int]], name: str = "a.pdf") -> Source:
    return Source(dateiname=name, fassung="x", text=text, seiten=1,
                  stuecke=[Piece(seite=1, von=v, bis=b) for v, b in stuecke])


def _antwort(*eintraege) -> str:
    return json.dumps({"facts": list(eintraege)})


def _e(piece=0, fact="Eine Aussage.", category="Zahl", citation="Beleg."):
    return {"piece": piece, "category": category, "fact": fact, "citation": citation}


# ── Auftragstext ─────────────────────────────────────────────────────────────

def test_jedes_stueck_steht_hinter_seiner_nummer():
    quelle = _quelle("AAAABBBB", [(0, 4), (4, 8)])
    assert numbered_pieces(quelle, 0, 2) == "[0] AAAA\n\n[1] BBBB"


def test_ein_ausschnitt_behaelt_die_echten_nummern():
    """Wird eine grosse Datei in zwei Aufrufen gelesen, verschieben sich die Nummern nie."""
    quelle = _quelle("AAAABBBBCCCC", [(0, 4), (4, 8), (8, 12)])
    assert numbered_pieces(quelle, 1, 3) == "[1] BBBB\n\n[2] CCCC"


def test_ueber_das_ende_hinaus_wird_nicht_erfunden():
    quelle = _quelle("AAAA", [(0, 4)])
    assert numbered_pieces(quelle, 0, 9) == "[0] AAAA"


def test_der_auftrag_nennt_das_raster_und_die_stuecknummern():
    text = system_prompt("de", ("Zahl", "Begriff"), teil=1, teile=1)
    assert "- Zahl" in text and "- Begriff" in text
    assert "square brackets" in text
    assert "part 1 of" not in text


def test_ein_teil_weiss_dass_er_ein_teil_ist():
    text = system_prompt("de", ("Zahl",), teil=2, teile=2)
    assert "part 2 of 2" in text
    assert "never describe the document as a whole" in text


# ── Antwort lesen ────────────────────────────────────────────────────────────

def test_eine_saubere_antwort_wird_gelesen():
    aus = parse_answer(_antwort(_e(piece=1)), gueltige_stuecke=range(0, 3))
    assert aus == [{"piece": 1, "category": "Zahl", "fact": "Eine Aussage.", "citation": "Beleg."}]


def test_eine_erfundene_stuecknummer_faellt_weg():
    """Sonst zeigt der Rueckweg spaeter auf den falschen Text."""
    aus = parse_answer(_antwort(_e(piece=99)), gueltige_stuecke=range(0, 3))
    assert aus == []


def test_eine_nummer_aus_einem_anderen_teil_faellt_weg():
    aus = parse_answer(_antwort(_e(piece=0)), gueltige_stuecke=range(5, 9))
    assert aus == []


def test_ohne_nummer_faellt_der_eintrag_weg():
    roh = json.dumps({"facts": [{"category": "Zahl", "fact": "A", "citation": "B"}]})
    assert parse_answer(roh, gueltige_stuecke=range(0, 3)) == []


def test_eine_leere_aussage_faellt_weg():
    aus = parse_answer(_antwort(_e(fact="   ")), gueltige_stuecke=range(0, 3))
    assert aus == []


def test_zu_lange_felder_werden_gekappt():
    aus = parse_answer(_antwort(_e(fact="a" * 900, category="b" * 90)),
                       gueltige_stuecke=range(0, 3))
    assert len(aus[0]["fact"]) == MAX_FACT_CHARS
    assert len(aus[0]["category"]) == MAX_CATEGORY_CHARS


def test_ein_denkblock_und_ein_zaun_werden_abgestreift():
    roh = "<think>ueberlege</think>\n```json\n" + _antwort(_e()) + "\n```"
    assert parse_answer(roh, gueltige_stuecke=range(0, 3))[0]["fact"] == "Eine Aussage."


def test_kein_json_gibt_nichts():
    assert parse_answer("Tut mir leid.", gueltige_stuecke=range(0, 3)) == []


def test_eine_abgeschnittene_antwort_verliert_nur_den_rest():
    roh = _antwort(_e(fact="Eins."), _e(fact="Zwei."))
    abgeschnitten = roh[:roh.index('"fact": "Zwei."') + 10]
    gerettet = parse_answer(abgeschnitten, gueltige_stuecke=range(0, 3))
    assert [g["fact"] for g in gerettet] == ["Eins."]


def test_salvage_findet_die_fertigen_objekte():
    assert len(salvage('[{"a": 1}, {"b": 2}, {"c":')) == 2


# ── Vorrat ───────────────────────────────────────────────────────────────────

def test_der_vorrat_zaehlt_ueber_alle_quellen_durch():
    vorrat = build_pool([[_e(fact="Eins.")], [_e(fact="Zwei.")]])
    assert [f.fact_id for f in vorrat] == [1, 2]
    assert [f.source for f in vorrat] == [0, 1]


def test_wiederholungen_innerhalb_einer_quelle_fallen_weg():
    vorrat = build_pool([[_e(fact="Gleich."), _e(fact="Gleich.")]])
    assert len(vorrat) == 1


def test_zwischen_quellen_wird_nichts_entfernt():
    """Zwei Quellen mit derselben Aussage sind Uebereinstimmung, kein Muell."""
    vorrat = build_pool([[_e(fact="Die Frist betraegt 30 Tage.")],
                         [_e(fact="Die Frist betraegt 30 Tage.")]])
    assert len(vorrat) == 2


def test_die_vollstaendigere_aussage_bleibt():
    kurz = "Die Frist betraegt dreissig volle Kalendertage ab Zugang."
    lang = kurz + " Im Haertefall sind es sechzig."
    vorrat = build_pool([[_e(fact=kurz), _e(fact=lang)]])
    assert [f.fact for f in vorrat] == [lang]


def test_kurze_aehnliche_aussagen_bleiben_beide():
    """Unter der Laengengrenze heisst Enthaltensein nicht dieselbe Aussage."""
    assert len(unique_within(["30 Tage.", "30 Tage ab Zugang."])) == 2


def test_der_block_traegt_nummer_kategorie_und_aussage_ohne_beleg():
    vorrat = build_pool([[_e(fact="Eine Aussage.", citation="Der Beleg.")]])
    block = pool_block(vorrat)
    assert block == "#1 (Zahl) Eine Aussage."
    assert "Der Beleg." not in block


def test_gesuchte_nummern_kommen_in_der_reihenfolge_des_vorrats():
    vorrat = build_pool([[_e(fact="Eins."), _e(fact="Zwei."), _e(fact="Drei.")]])
    assert [f.fact for f in facts_for([3, 1], vorrat)] == ["Eins.", "Drei."]


def test_unbekannte_nummern_fallen_weg():
    vorrat = build_pool([[_e(fact="Eins.")]])
    assert facts_for([99], vorrat) == []


def test_ein_fakt_kommt_unveraendert_zurueck():
    fakt = Fact(fact_id=1, category="Zahl", fact="A", citation="B", source=0, piece=2)
    assert from_dict(fakt.as_dict()) == fakt


def test_ein_beschaedigter_fakt_gibt_none():
    assert from_dict({"fact_id": "x"}) is None


# ── Rückweg in den Text ──────────────────────────────────────────────────────

def test_der_rueckweg_holt_das_stueck_und_seine_nachbarn():
    quelle = _quelle("AAAABBBBCCCCDDDD", [(0, 4), (4, 8), (8, 12), (12, 16)])
    fakt = Fact(fact_id=1, category="Zahl", fact="x", citation="y", source=0, piece=1)
    assert context_for([fakt], [quelle], nachbarn=1) == "AAAABBBBCCCC"


def test_ohne_nachbarn_kommt_nur_das_stueck():
    quelle = _quelle("AAAABBBBCCCC", [(0, 4), (4, 8), (8, 12)])
    fakt = Fact(fact_id=1, category="Zahl", fact="x", citation="y", source=0, piece=1)
    assert context_for([fakt], [quelle], nachbarn=0) == "BBBB"


def test_am_rand_wird_nicht_ueber_die_quelle_hinaus_gegriffen():
    quelle = _quelle("AAAABBBB", [(0, 4), (4, 8)])
    fakt = Fact(fact_id=1, category="Zahl", fact="x", citation="y", source=0, piece=0)
    assert context_for([fakt], [quelle], nachbarn=5) == "AAAABBBB"


def test_benachbarte_stuecke_werden_zu_einer_stelle_verbunden():
    quelle = _quelle("AAAABBBBCCCCDDDD", [(0, 4), (4, 8), (8, 12), (12, 16)])
    fakten = [Fact(fact_id=1, category="Zahl", fact="x", citation="y", source=0, piece=0),
              Fact(fact_id=2, category="Zahl", fact="x", citation="y", source=0, piece=1)]
    assert context_for(fakten, [quelle], nachbarn=0) == "AAAABBBB"


def test_entfernte_stellen_bleiben_getrennt():
    quelle = _quelle("AAAABBBBCCCCDDDD", [(0, 4), (4, 8), (8, 12), (12, 16)])
    fakten = [Fact(fact_id=1, category="Zahl", fact="x", citation="y", source=0, piece=0),
              Fact(fact_id=2, category="Zahl", fact="x", citation="y", source=0, piece=3)]
    assert context_for(fakten, [quelle], nachbarn=0) == "AAAA\n\nDDDD"


def test_stellen_aus_zwei_quellen_kommen_beide():
    a = _quelle("AAAA", [(0, 4)], "a.pdf")
    b = _quelle("BBBB", [(0, 4)], "b.pdf")
    fakten = [Fact(fact_id=1, category="Zahl", fact="x", citation="y", source=0, piece=0),
              Fact(fact_id=2, category="Zahl", fact="x", citation="y", source=1, piece=0)]
    assert context_for(fakten, [a, b], nachbarn=0) == "AAAA\n\nBBBB"


def test_eine_quelle_die_es_nicht_mehr_gibt_stuerzt_nicht_ab():
    quelle = _quelle("AAAA", [(0, 4)])
    fakt = Fact(fact_id=1, category="Zahl", fact="x", citation="y", source=7, piece=0)
    assert context_for([fakt], [quelle]) == ""


# ── Vorrat als Lesestoff für ein Werkzeug, das in einem Aufruf schreibt ──────

def test_der_lesestoff_traegt_aussage_und_beleg():
    from src.services.facts import material_block

    vorrat = build_pool([[_e(fact="Eine Aussage.", citation="Der Beleg.")]])
    assert material_block(vorrat, 10_000) == '- Eine Aussage. Beleg: "Der Beleg."'


def test_ohne_beleg_steht_nur_die_aussage():
    from src.services.facts import material_block

    vorrat = build_pool([[_e(fact="Eine Aussage.", citation="")]])
    assert material_block(vorrat, 10_000) == "- Eine Aussage."


def test_der_lesestoff_haelt_sein_budget_ein():
    from src.services.facts import material_block

    vorrat = build_pool([[_e(fact=f"Aussage {i}.") for i in range(200)]])
    block = material_block(vorrat, 500)
    assert len(block) <= 500


def test_der_dateiname_kommt_im_lesestoff_nicht_vor():
    from src.services.facts import material_block

    vorrat = build_pool([[_e(fact="Eine Aussage.")]])
    assert "a.pdf" not in material_block(vorrat, 10_000)
