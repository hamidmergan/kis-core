"""An appointment without a day must not claim one, the first only sorts."""

from datetime import date

from src.features.ai_assistant.tasks.studio.schedule._titles import _find_merge_target


def _eintrag(id_, due_date, title, precision="day"):
    return {"id": id_, "due_date": due_date, "title": title,
            "date_precision": precision, "source_refs": []}


def test_monat_und_monatserster_sind_nicht_dasselbe():
    """Both sit on 1 July but mean different things."""
    vorhanden = [_eintrag(1, date(2026, 7, 1), "Abgabe Hausarbeit", "month")]

    ziel = _find_merge_target(vorhanden, date(2026, 7, 1), "day",
                              "Abgabe Hausarbeit", {"raw_quote": "Abgabe am 01.07.2026"})

    assert ziel is None


def test_zwei_monatstermine_kommen_zusammen():
    vorhanden = [_eintrag(1, date(2026, 7, 1), "Abgabe Hausarbeit", "month")]

    ziel = _find_merge_target(vorhanden, date(2026, 7, 1), "month",
                              "Abgabe Hausarbeit", {"raw_quote": "im Juli 2026"})

    assert ziel is not None and ziel["id"] == 1


def test_zwei_taggenaue_termine_kommen_weiterhin_zusammen():
    vorhanden = [_eintrag(1, date(2026, 7, 3), "Abgabe Hausarbeit")]

    ziel = _find_merge_target(vorhanden, date(2026, 7, 3), "day",
                              "Abgabe Hausarbeit", {"raw_quote": "03.07.2026"})

    assert ziel is not None and ziel["id"] == 1


def test_alte_eintraege_ohne_das_feld_gelten_als_taggenau():
    """Legacy from before the column, without a value the day is meant."""
    alt = {"id": 1, "due_date": date(2026, 7, 3), "title": "Abgabe Hausarbeit",
           "source_refs": []}

    ziel = _find_merge_target([alt], date(2026, 7, 3), "day",
                              "Abgabe Hausarbeit", {"raw_quote": "03.07.2026"})

    assert ziel is not None
