"""Ein Termin, bei dem nur der Monat bekannt ist, darf keinen Tag behaupten.

"Die Abgabe erfolgt im Juli 2026" nennt keinen Tag. Die Datenbank speichert aber einen
Tag, sonst laesst sich nichts einsortieren. Also traegt due_date den Monatsersten als
reinen Sortierpunkt und date_precision='month' sagt dazu: dieser Tag stand nirgends.

Die Ansicht zeigt daraufhin nur den Monat. Der 01.07. darf nicht als Frist erscheinen,
sonst haelt ihn jemand fuer den Abgabetermin.
"""

from datetime import date

from src.features.ai_assistant.tasks.studio.schedule._titles import _find_merge_target


def _eintrag(id_, due_date, title, precision="day"):
    return {"id": id_, "due_date": due_date, "title": title,
            "date_precision": precision, "source_refs": []}


def test_monat_und_monatserster_sind_nicht_dasselbe():
    """Beide liegen auf dem 01.07., meinen aber Verschiedenes."""
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
    """Bestand aus der Zeit vor der Spalte. Ohne Angabe ist der Tag gemeint."""
    alt = {"id": 1, "due_date": date(2026, 7, 3), "title": "Abgabe Hausarbeit",
           "source_refs": []}

    ziel = _find_merge_target([alt], date(2026, 7, 3), "day",
                              "Abgabe Hausarbeit", {"raw_quote": "03.07.2026"})

    assert ziel is not None
