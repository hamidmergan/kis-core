"""The shared title logic, the list of taken titles comes in from outside."""

from src.features.ai_assistant.tasks._titles import (
    MAX_TITLE_LEN,
    is_title_taken,
    next_free_counter,
)


def test_is_title_taken_erkennt_den_einen_buchstaben_unterschied():
    assert is_title_taken("Wissenschaftliches Arbeiten", ["Wissenschaftliche Arbeiten"])


def test_next_free_counter_zaehlt_ueber_die_ganze_familie():
    assert next_free_counter("Titel", ["Titel", "Titel (2)"]) == "Titel (3)"


def test_max_title_len_ist_die_eine_obergrenze():
    assert MAX_TITLE_LEN == 120
