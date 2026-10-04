"""Orte in Antworten: Gebäudecodes und Namen zählen, Wortteile nicht."""
from src.features.campus.services.place_match import find_places, show_param

ORTE = [
    {"id": "Mensa_B_59", "code": "B.59", "kind": "building", "title": {"de": "Mensa B.59", "en": "Mensa (Dining Hall) B.59"},
     "name": {"de": "Mensa", "en": "Mensa (dining hall)"}, "facilities": [{"de": "Mensa", "en": "Mensa (dining hall)"}]},
    {"id": "Gebaeude_A_1", "code": "A.1", "kind": "building", "title": {"de": "Gebäude A.1", "en": "Building A.1"},
     "facilities": [{"de": "International Office", "en": "International Office"}, {"de": "Studienberatung", "en": "Student Advisory Service"}]},
    {"id": "MFC_7", "code": "MFC 7", "kind": "building", "title": {"de": "MFC 7", "en": "MFC 7"}},
    {"id": "Kaffee_Cafeteria", "code": None, "kind": "food", "title": {"de": "Cafeteria", "en": "Cafeteria"}},
]


def test_code_und_name_finden_den_ort():
    karten = find_places("Die Mensa liegt im Gebäude B.59 neben der Bibliothek.", ORTE)
    assert [k["id"] for k in karten] == ["Mensa_B_59"]
    assert karten[0]["show"] == "B.59"


def test_nur_ein_ort_der_zuerst_genannte():
    karten = find_places("Das International Office findest du in A.1, die Mensa daneben.", ORTE)
    assert [k["id"] for k in karten] == ["Gebaeude_A_1"]


def test_wortteile_zaehlen_nicht():
    assert find_places("Der Mensaplan steht online.", ORTE) == []
    assert find_places("Siehe Anlage A.10 im Vertrag.", ORTE) == []


def test_codes_mit_und_ohne_trenner():
    assert [k["id"] for k in find_places("Raum MFC7 oder MFC 7, egal.", ORTE)] == ["MFC_7"]
    assert [k["id"] for k in find_places("Treffpunkt A1 vor dem Eingang.", ORTE)] == ["Gebaeude_A_1"]


def test_unbekannt_und_grenze():
    assert find_places("Das Rathaus ist in der Innenstadt.", ORTE) == []
    viele = find_places("A.1, B.59, MFC 7 und die Cafeteria.", ORTE, limit=3)
    assert len(viele) == 3


def test_show_parameter_ohne_code_nimmt_die_id():
    assert show_param(ORTE[3]) == "Kaffee_Cafeteria"
    assert show_param(ORTE[2]) == "MFC7"
