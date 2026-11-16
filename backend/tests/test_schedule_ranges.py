"""A span is one appointment: stored pairings, the resolved end and the merge."""

from datetime import date

from src.features.ai_assistant.tasks.studio.schedule import _split_rejected_ranges
from src.features.ai_assistant.tasks.studio.schedule._parse import _range_end_date
from src.features.ai_assistant.tasks.studio.schedule._titles import _find_merge_target


# --- stored analyses of the earlier pipeline --------------------------------------

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
    """Whatever the classification discards anyway needs no second date."""
    cands, _ = _split_rejected_ranges(
        [_cand("2026-09-01", "2026-09-27")], [_cls(keep=False)])

    assert len(cands) == 1


def test_termin_ohne_zweites_datum_bleibt_unberuehrt():
    cands, _ = _split_rejected_ranges([_cand("2026-09-25")], [_cls()])

    assert len(cands) == 1


# --- the resolved end date ----------------------------------------------------

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
