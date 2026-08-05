"""Zeitgrenzen der KI-Tutor-Aufträge.

Ein Zeitüberlauf wirft die ganze Arbeit weg und der Lernende sieht nur
"fehlgeschlagen". Die Grenzen standen deshalb lange zu knapp und als nackte Zahl
in vier verschiedenen Dekoratoren. Hier steht fest, was sie leisten müssen.
"""

import pytest

from src.limits import (
    AIA_SCHEDULE_SOFT_TIME_LIMIT,
    AIA_SCHEDULE_TIME_LIMIT,
    AIA_TOOL_SOFT_TIME_LIMIT,
    AIA_TOOL_TIME_LIMIT,
)


def _limits(task):
    return task.soft_time_limit, task.time_limit


def _tasks():
    from src.features.ai_assistant.tasks.language_training import run_generate_exercise_set
    from src.features.ai_assistant.tasks.studio.data_table import run_generate_data_table
    from src.features.ai_assistant.tasks.studio.mindmap import run_generate_mindmap
    return {
        "exercise_set": run_generate_exercise_set,
        "data_table": run_generate_data_table,
        "mindmap": run_generate_mindmap,
    }


@pytest.mark.parametrize("name", ["exercise_set", "data_table", "mindmap"])
def test_every_tool_job_gets_the_same_five_minutes(name):
    """Gemessen am 2026-08-05: der langsamste von sieben Läufen brauchte 74 der
    alten 120 Sekunden, und das auf einer schnellen Maschine. Das Schreibtempo des
    Anbieters schwankt um den Faktor 25, also reisst derselbe Lauf die alte Grenze
    ohne jeden Fehler im Code. Ein Übungs-Set ist ausserdem kein einzelner Aufruf,
    sondern eine Kette aus Generierung, Nachschlag und Titel."""
    soft, hard = _limits(_tasks()[name])
    assert soft == AIA_TOOL_SOFT_TIME_LIMIT == 300
    assert hard == AIA_TOOL_TIME_LIMIT == 360


def test_the_schedule_keeps_its_longer_window():
    # Der Zeitplan geht über den ganzen Kurs, nicht über einen Satz Aufgaben.
    from src.features.ai_assistant.tasks.studio.schedule import run_generate_schedule
    assert _limits(run_generate_schedule) == (AIA_SCHEDULE_SOFT_TIME_LIMIT,
                                              AIA_SCHEDULE_TIME_LIMIT)


@pytest.mark.parametrize("soft, hard", [
    (AIA_TOOL_SOFT_TIME_LIMIT, AIA_TOOL_TIME_LIMIT),
    (AIA_SCHEDULE_SOFT_TIME_LIMIT, AIA_SCHEDULE_TIME_LIMIT),
])
def test_the_hard_stop_leaves_a_minute_to_fail_cleanly(soft, hard):
    """Die weiche Grenze wirft SoftTimeLimitExceeded, der Auftrag setzt das Set auf
    fehlgeschlagen und räumt auf. Fällt die harte Grenze zu dicht dahinter, wird der
    Prozess mitten im Aufräumen abgeschossen und das Set bleibt auf "wird generiert"
    stehen."""
    assert hard - soft >= 60
