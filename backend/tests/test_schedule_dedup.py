"""Candidates that ask the model the same question are classified once."""

from src.features.ai_assistant.tasks.studio.schedule._dedup import group_for_classification


def _cand(iso: str, context: str, **extra) -> dict:
    return {"date_iso": iso, "partial_date": None, "is_tbd": False,
            "context": context, **extra}


def test_the_same_date_in_the_same_wording_is_asked_once():
    cands = [
        _cand("2009-07-29", "Fußnote § 2 Abs. 4 idF d. G v. 29.7.2009 I 2542: Bayern"),
        _cand("2009-07-29", "Fußnote § 7 Abs. 1 idF d. G v. 29.7.2009 I 2542: Bayern"),
    ]
    reps, mapping = group_for_classification(cands)
    assert len(reps) == 1
    assert mapping == [0, 0]


def test_the_same_date_in_different_wording_is_asked_twice():
    cands = [
        _cand("2026-03-14", "Die Klausur findet am 14.03.2026 statt"),
        _cand("2026-03-14", "Stand: 14.03.2026, Prof. Dr. Meier"),
    ]
    reps, mapping = group_for_classification(cands)
    assert len(reps) == 2
    assert mapping == [0, 1]


def test_different_dates_in_the_same_wording_stay_apart():
    cands = [
        _cand("2026-03-14", "Die Klausur findet am 14.03.2026 statt"),
        _cand("2026-05-02", "Die Klausur findet am 02.05.2026 statt"),
    ]
    reps, mapping = group_for_classification(cands)
    assert len(reps) == 2


def test_the_representative_is_the_first_of_its_group():
    cands = [
        _cand("2026-03-14", "Stand: 14.03.2026, Meier"),
        _cand("2009-07-29", "Fußnote § 2 idF d. G v. 29.7.2009"),
        _cand("2009-07-29", "Fußnote § 9 idF d. G v. 29.7.2009"),
    ]
    reps, mapping = group_for_classification(cands)
    assert reps[0] is cands[0]
    assert reps[1] is cands[1]
    assert mapping == [0, 1, 1]


def test_an_open_appointment_groups_on_its_wording():
    a = {"date_iso": None, "partial_date": None, "is_tbd": True,
         "context": "Der Termin fuer die Exkursion wird noch bekannt gegeben"}
    b = dict(a)
    reps, mapping = group_for_classification([a, b])
    assert len(reps) == 1


def test_an_empty_list_stays_empty():
    assert group_for_classification([]) == ([], [])
