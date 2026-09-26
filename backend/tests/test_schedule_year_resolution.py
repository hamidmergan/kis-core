"""A date without a year gets its nearest occurrence, a year written elsewhere wins."""

from datetime import date

from src.features.ai_assistant.tasks.studio.schedule._parse import (
    _candidate_start,
    _range_end_date,
    _resolve_year,
    _year_evidence,
)

HEUTE = date(2026, 9, 26)


def test_vergangener_januar_rutscht_ins_naechste_jahr():
    assert _resolve_year(HEUTE, 1, 10) == (date(2027, 1, 10), True)


def test_termin_von_letzter_woche_bleibt_im_laufenden_jahr():
    assert _resolve_year(HEUTE, 9, 19) == (date(2026, 9, 19), True)


def test_kommender_termin_im_laufenden_jahr():
    assert _resolve_year(HEUTE, 11, 2) == (date(2026, 11, 2), True)


def test_im_januar_ist_der_dezember_der_vergangene():
    assert _resolve_year(date(2027, 1, 5), 12, 20) == (date(2026, 12, 20), True)


def test_29_februar_nimmt_das_naechste_schaltjahr_in_reichweite():
    assert _resolve_year(date(2027, 9, 1), 2, 29) == (date(2028, 2, 29), True)


def test_29_februar_ohne_schaltjahr_in_reichweite_faellt_weg():
    assert _resolve_year(date(2026, 9, 1), 2, 29) == (None, False)


def test_ein_geschriebenes_jahr_schlaegt_die_annahme():
    beleg = {(1, 10): {2026}}
    assert _resolve_year(HEUTE, 1, 10, beleg) == (date(2026, 1, 10), False)


def test_belege_kommen_aus_kandidaten_und_bestehenden_eintraegen():
    beleg = _year_evidence(
        [{"date_iso": "2027-01-10", "date_precision": "day"},
         {"date_iso": "2027-03-01", "date_precision": "month"}],
        [{"due_date": date(2026, 12, 3), "date_precision": "day"},
         {"due_date": date(2027, 2, 1), "date_precision": "day", "year_assumed": True}],
    )
    assert beleg == {(1, 10): {2027}, (12, 3): {2026}}


def test_kandidat_ohne_jahr_ist_als_annahme_markiert():
    cand = {"date_iso": None, "partial_date": [1, 10]}
    assert _candidate_start(cand, HEUTE) == (date(2027, 1, 10), True)


def test_kandidat_mit_jahr_ist_keine_annahme():
    cand = {"date_iso": "2026-01-10", "partial_date": None}
    assert _candidate_start(cand, HEUTE) == (date(2026, 1, 10), False)


def test_offener_termin_hat_kein_datum():
    assert _candidate_start({"is_tbd": True}, HEUTE) == (None, False)


def test_geschriebenes_ende_legt_das_jahr_des_anfangs_fest():
    cand = {"date_iso": None, "partial_date": [12, 20], "date_end_iso": "2028-01-10"}
    assert _candidate_start(cand, HEUTE, use_end=True) == (date(2027, 12, 20), False)


def test_ende_ohne_bestaetigte_spanne_zaehlt_nicht():
    cand = {"date_iso": None, "partial_date": [12, 20], "date_end_iso": "2028-01-10"}
    assert _candidate_start(cand, HEUTE) == (date(2026, 12, 20), True)


def test_jahrloses_ende_folgt_dem_anfang_ueber_den_jahreswechsel():
    cand = {"date_end_partial": (1, 10)}
    assert _range_end_date(cand, date(2026, 12, 20), HEUTE) == date(2027, 1, 10)


def test_jahrloses_ende_ohne_anfang_nimmt_das_naechste_vorkommen():
    cand = {"date_end_partial": (1, 10)}
    assert _range_end_date(cand, None, HEUTE) == date(2027, 1, 10)


# --- the model may not fill in a year the text does not write ------------------

def _paar(text, datum, ende=None):
    from src.features.ai_assistant.tasks.studio.schedule._extract import items_to_pairs
    block = {"id": 1, "text": text, "source_id": 7, "source_uuid": "u7",
             "source_filename": "plan.pdf", "page_number": 1, "start_time": None}
    item = {"id": 1, "date": datum, "end_date": ende, "type": "termin",
            "title": "Klausur", "quote": text}
    return items_to_pairs([item], [block], HEUTE)[7][0][0]


def test_ein_erfundenes_jahr_wird_wieder_zur_jahrlosen_angabe():
    c = _paar("Die Webkonferenz war am 22. September um 17:30 Uhr.", "2026-09-22")
    assert (c["date_iso"], c["partial_date"], c["date_precision"]) == (None, (9, 22), "day")


def test_ein_geschriebenes_jahr_bleibt():
    c = _paar("Klausur am 10. Januar 2027.", "2027-01-10")
    assert (c["date_iso"], c["partial_date"]) == ("2027-01-10", None)


def test_das_kurze_jahr_eines_zahlendatums_zaehlt_als_geschrieben():
    c = _paar("Klausur am 10.1.27", "2027-01-10")
    assert c["date_iso"] == "2027-01-10"


def test_ein_erfundenes_jahr_beim_monat_wird_zum_blossen_monat():
    c = _paar("Abgabe Ende Mai.", "2026-05")
    assert (c["date_iso"], c["partial_date"], c["date_precision"]) == (None, (5, 1), "month")


def test_ein_erfundenes_jahr_am_ende_wird_jahrlos():
    c = _paar("vom 20. Dezember bis 10. Januar", "12-20", ende="2027-01-10")
    assert (c["date_end_iso"], c["date_end_partial"]) == (None, (1, 10))


def test_ein_jahr_aus_einer_anderen_zeile_zaehlt_nicht():
    from src.features.ai_assistant.tasks.studio.schedule._extract import items_to_pairs
    text = "Abgabe bis zum 15.11.2026.\nDie Webkonferenz war am 22. September."
    block = {"id": 1, "text": text, "source_id": 7, "source_uuid": "u7",
             "source_filename": "plan.pdf", "page_number": 1, "start_time": None}
    item = {"id": 1, "date": "2026-09-22", "type": "termin", "title": "Webkonferenz",
            "quote": "Die Webkonferenz war am 22. September."}
    c = items_to_pairs([item], [block], HEUTE)[7][0][0]
    assert (c["date_iso"], c["partial_date"]) == (None, (9, 22))


def test_eine_andere_zahl_ist_kein_jahr():
    c = _paar("Raum 12026, am 22. September", "2026-09-22")
    assert c["date_iso"] is None
