"""Zeitspannen: "28.09.2026 bis 02.11.2026" ist EIN Termin, nicht zwei.

Bis hierhin fand der Kandidatenschritt jedes Datum einzeln. Aus einer Zeile des
Terminplans wurden zwei Karten, eine am Anfang mit "bis 02.11.2026" im Text und eine am
Ende mit "ab 28.09.2026". Am echten MIM-Terminplan waren 9 von 22 Karten solche
Dubletten.

Die Arbeitsteilung ist dieselbe wie ueberall im Zeitplan: der Regex SCHLAEGT eine
Paarung VOR, er sieht nur den Abstand und was dazwischen nicht stehen darf. Ob es
wirklich eine Spanne ist, entscheidet die Klassifikation mit dem ganzen Zusammenhang.
Lehnt sie ab, wird die Paarung wieder zu zwei Terminen, damit die Erkennung nie
schlechter ist als der Stand ohne sie.
"""

from datetime import date

import pytest

from src.features.ai_assistant.tasks.studio.schedule import _candidates as cand_mod
from src.features.ai_assistant.tasks.studio.schedule import _split_rejected_ranges
from src.features.ai_assistant.tasks.studio.schedule._parse import _range_end_date
from src.features.ai_assistant.tasks.studio.schedule._regex import _looks_like_range
from src.features.ai_assistant.tasks.studio.schedule._titles import _find_merge_target


def _src():
    return {"id": 1, "uuid": "u-1", "filename": "terminplan.pdf"}


def _chunks(*texts):
    return [
        {"id": i, "content": t, "page_number": i + 1, "start_time": None}
        for i, t in enumerate(texts)
    ]


def _luecke(text):
    """Der Abstand zwischen den ersten beiden Daten des Textes."""
    from src.features.ai_assistant.tasks.studio.schedule._regex import _date_candidates_in_text
    funde = _date_candidates_in_text(text)
    assert len(funde) >= 2, funde
    return _looks_like_range(text, funde[0][1], funde[1][0])


# --- was der Regex vorschlaegt ------------------------------------------------

@pytest.mark.parametrize("text", [
    "28.09.2026 bis 02.11.2026 Online-Anmeldung",
    "28.09.2026 - 02.11.2026 Online-Anmeldung",
    "28.09.2026 – 02.11.2026",
    "vom 03.07.2026 bis zum 17.07.2026",
    "28.09.2026    bis     02.11.2026 Betreuungszeit",
    "01.09.2026 hasta 27.09.2026",
])
def test_zwei_daten_mit_verbindungswort_sind_eine_spanne(text):
    assert _luecke(text) is True


@pytest.mark.parametrize("text,warum", [
    ("Zwischenbericht 30.04.2026, 15.05.2026", "Komma heisst Aufzaehlung"),
    ("30.04.2026; 15.05.2026", "Semikolon heisst Aufzaehlung"),
    ("01.09.2026    27.09.2026    Belegung", "nichts dazwischen sind zwei Spalten"),
    ("01.09.2026 | 27.09.2026", "Spaltenstrich trennt"),
    ("Abgabe 01.09.2026\nKlausur 27.09.2026", "Zeilenumbruch trennt"),
    ("01.09.2026 und 3 Wochen spaeter 27.09.2026", "zu weit auseinander"),
])
def test_was_keine_spanne_ist(text, warum):
    assert _luecke(text) is False, warum


def test_auch_ausgeschriebene_daten_bilden_eine_spanne(monkeypatch):
    """Was das Modell liest ("3 Temmuz 2026"), wird genauso gepaart wie die Ziffernform.

    Sonst haetten nur deutsche und englische Quellen Zeitspannen.
    """
    import json, types
    chunks = _chunks("Sinav 3 Temmuz 2026 kadar 17 Temmuz 2026 arasinda")
    monkeypatch.setattr(cand_mod.db, "get_aia_chunks_by_source", lambda _id: chunks)

    def create(model, messages, **kwargs):
        inhalt = json.dumps({"dates": [
            {"id": 0, "phrase": "3 Temmuz 2026", "date": "2026-07-03"},
            {"id": 0, "phrase": "17 Temmuz 2026", "date": "2026-07-17"},
        ]})
        return types.SimpleNamespace(
            choices=[types.SimpleNamespace(message=types.SimpleNamespace(content=inhalt))])

    client = types.SimpleNamespace(
        chat=types.SimpleNamespace(completions=types.SimpleNamespace(create=create)))

    out = cand_mod._build_candidates_for_source(_src(), client=client, model="m")

    assert len(out) == 1
    assert out[0]["date_iso"] == "2026-07-03"
    assert out[0]["date_end_iso"] == "2026-07-17"


def test_ein_wort_dazwischen_wird_vorgeschlagen_aber_nicht_entschieden():
    """"Abgabe 01.09.2026 Klausur 27.09.2026" sieht wie eine Spanne aus.

    Der Regex kann das nicht unterscheiden, er schlaegt vor. Verworfen wird es weiter
    unten von der Klassifikation, siehe test_abgelehnte_paarung_wird_wieder_zu_zwei.
    """
    assert _luecke("Abgabe 01.09.2026 Klausur 27.09.2026") is True


# --- was daraus als Kandidat wird ---------------------------------------------

def test_spanne_wird_ein_kandidat_statt_zwei(monkeypatch):
    chunks = _chunks("28.09.2026 bis 02.11.2026 Online-Anmeldung zu den "
                     "Prüfungsvorleistungen über das QIS-System")
    monkeypatch.setattr(cand_mod.db, "get_aia_chunks_by_source", lambda _id: chunks)

    out = cand_mod._build_candidates_for_source(_src())

    assert len(out) == 1
    assert out[0]["date_iso"] == "2026-09-28"
    assert out[0]["date_end_iso"] == "2026-11-02"
    assert out[0]["date_end_raw"] == "02.11.2026"


def test_der_beleg_reicht_ueber_beide_daten(monkeypatch):
    chunks = _chunks("28.09.2026 bis 02.11.2026 Online-Anmeldung")
    monkeypatch.setattr(cand_mod.db, "get_aia_chunks_by_source", lambda _id: chunks)

    out = cand_mod._build_candidates_for_source(_src())

    assert "02.11.2026" in out[0]["raw_quote"]


def test_das_ende_erbt_das_jahr_des_anfangs(monkeypatch):
    chunks = _chunks("Anmeldung 28.09.2026 bis 02.11.")
    monkeypatch.setattr(cand_mod.db, "get_aia_chunks_by_source", lambda _id: chunks)

    out = cand_mod._build_candidates_for_source(_src())

    assert len(out) == 1
    assert out[0]["date_end_iso"] == "2026-11-02"


def test_ueber_den_jahreswechsel_zaehlt_das_naechste_jahr(monkeypatch):
    chunks = _chunks("Rückmeldung 28.12.2026 bis 02.01.")
    monkeypatch.setattr(cand_mod.db, "get_aia_chunks_by_source", lambda _id: chunks)

    out = cand_mod._build_candidates_for_source(_src())

    assert out[0]["date_end_iso"] == "2027-01-02"


def test_rueckwaerts_ist_keine_spanne(monkeypatch):
    chunks = _chunks("02.11.2026 bis 28.09.2026")
    monkeypatch.setattr(cand_mod.db, "get_aia_chunks_by_source", lambda _id: chunks)

    out = cand_mod._build_candidates_for_source(_src())

    assert len(out) == 2
    assert all(c["date_end_iso"] is None for c in out)


def test_ein_monat_ohne_tag_taugt_nicht_als_ende(monkeypatch):
    """"ab 03.07.2026 bis 11.2026": der Erste oder der Letzte des Monats? Unklar."""
    chunks = _chunks("Laufzeit 03.07.2026 bis 11.2026")
    monkeypatch.setattr(cand_mod.db, "get_aia_chunks_by_source", lambda _id: chunks)

    out = cand_mod._build_candidates_for_source(_src())

    assert out[0]["date_end_iso"] is None


def test_aufzaehlung_bleibt_bei_zwei_kandidaten(monkeypatch):
    chunks = _chunks("Zwischenberichte am 30.04.2026, 15.05.2026")
    monkeypatch.setattr(cand_mod.db, "get_aia_chunks_by_source", lambda _id: chunks)

    out = cand_mod._build_candidates_for_source(_src())

    assert [c["date_iso"] for c in out] == ["2026-04-30", "2026-05-15"]


def test_die_ganze_terminplan_zeile_ergibt_genau_einen_termin(monkeypatch):
    """Sechs Zeilen aus dem echten MIM-Plan, vier davon Spannen."""
    chunks = _chunks(
        "01.09.2026 bis 27.09.2026 Belegung der Module\n"
        "25.09.2026 Begrüßung der Studienanfängerinnen\n"
        "28.09.2026 bis 21.01.2027 Betreuungszeit für die Module\n"
        "28.09.2026 bis 02.11.2026 Online-Anmeldung zu den Prüfungsvorleistungen\n"
        "01.12.2026 bis 31.12.2026 Rückmeldung für das Sommersemester 2027\n"
        "bis 03.01.2027 Eingabe der Prüfungsvorleistungen"
    )
    monkeypatch.setattr(cand_mod.db, "get_aia_chunks_by_source", lambda _id: chunks)

    out = cand_mod._build_candidates_for_source(_src())

    assert len(out) == 6
    mit_ende = [(c["date_iso"], c["date_end_iso"]) for c in out if c["date_end_iso"]]
    assert mit_ende == [
        ("2026-09-01", "2026-09-27"),
        ("2026-09-28", "2027-01-21"),
        ("2026-09-28", "2026-11-02"),
        ("2026-12-01", "2026-12-31"),
    ]


# --- was die Klassifikation daraus macht --------------------------------------

def _cand(iso, ende=None, teil=None):
    return {"date_iso": iso, "date_end_iso": ende, "date_end_partial": teil,
            "date_end_raw": "02.11.2026" if (ende or teil) else None,
            "partial_date": None, "date_precision": "day"}


def _cls(keep=True, is_range=False):
    return {"keep": keep, "is_range": is_range, "is_footer": False,
            "title": "Online-Anmeldung", "type": "termin"}


def test_bestaetigte_spanne_bleibt_ein_termin():
    cands, cls = _split_rejected_ranges(
        [_cand("2026-09-28", "2026-11-02")], [_cls(is_range=True)])

    assert len(cands) == 1
    assert cands[0]["date_end_iso"] == "2026-11-02"


def test_abgelehnte_paarung_wird_wieder_zu_zwei():
    cands, cls = _split_rejected_ranges(
        [_cand("2026-09-01", "2026-09-27")], [_cls(is_range=False)])

    assert [c["date_iso"] for c in cands] == ["2026-09-01", "2026-09-27"]
    assert len(cls) == 2
    assert cands[1]["date_end_iso"] is None


def test_verworfener_kandidat_wird_nicht_aufgeteilt():
    """Was die Klassifikation ohnehin wegwirft, braucht kein zweites Datum."""
    cands, _ = _split_rejected_ranges(
        [_cand("2026-09-01", "2026-09-27")], [_cls(keep=False)])

    assert len(cands) == 1


def test_termin_ohne_zweites_datum_bleibt_unberuehrt():
    cands, _ = _split_rejected_ranges([_cand("2026-09-25")], [_cls()])

    assert len(cands) == 1


# --- das aufgeloeste Enddatum -------------------------------------------------

def test_ende_muss_nach_dem_anfang_liegen():
    heute = date(2026, 8, 25)
    assert _range_end_date(_cand("2026-09-28", "2026-09-28"), date(2026, 9, 28), heute) is None


def test_jahrloses_ende_landet_im_laufenden_jahr():
    heute = date(2026, 8, 25)
    ende = _range_end_date(_cand("2026-09-28", teil=(11, 2)), date(2026, 9, 28), heute)
    assert ende == date(2026, 11, 2)


def test_jahrloses_ende_vor_dem_anfang_rutscht_ins_folgejahr():
    heute = date(2026, 8, 25)
    ende = _range_end_date(_cand("2026-12-28", teil=(1, 2)), date(2026, 12, 28), heute)
    assert ende == date(2027, 1, 2)


# --- Zusammenfuehren ----------------------------------------------------------

def test_eine_spanne_frisst_keinen_einzeltermin_am_selben_starttag():
    einzeln = {"id": 1, "due_date": date(2026, 9, 28), "end_date": None,
               "date_precision": "day", "title": "Online-Anmeldung", "source_refs": []}

    ziel = _find_merge_target([einzeln], date(2026, 9, 28), "day",
                              "Online-Anmeldung", {"raw_quote": "x"},
                              end_date=date(2026, 11, 2))

    assert ziel is None


def test_zwei_gleiche_spannen_kommen_zusammen():
    spanne = {"id": 1, "due_date": date(2026, 9, 28), "end_date": date(2026, 11, 2),
              "date_precision": "day", "title": "Online-Anmeldung", "source_refs": []}

    ziel = _find_merge_target([spanne], date(2026, 9, 28), "day",
                              "Online-Anmeldung zu den Prüfungsvorleistungen",
                              {"raw_quote": "x"}, end_date=date(2026, 11, 2))

    assert ziel is spanne
