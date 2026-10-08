"""The timeouts of the tutor jobs and what they have to allow for."""

import pytest

from src.limits import (
    AIA_SCHEDULE_SOFT_TIME_LIMIT,
    AIA_SCHEDULE_TIME_LIMIT,
    AIA_TABLE_SOFT_TIME_LIMIT,
    AIA_TABLE_TIME_LIMIT,
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


@pytest.mark.parametrize("name", ["exercise_set", "mindmap"])
def test_a_single_call_tool_gets_ten_minutes(name):
    """An exercise set is a chain, and a local model writes slowly."""
    soft, hard = _limits(_tasks()[name])
    assert soft == AIA_TOOL_SOFT_TIME_LIMIT == 600
    assert hard == AIA_TOOL_TIME_LIMIT == 720


def test_the_table_gets_room_for_several_packets():
    # It asks packet by packet now, one window of five minutes no longer covers that.
    assert _limits(_tasks()["data_table"]) == (AIA_TABLE_SOFT_TIME_LIMIT, AIA_TABLE_TIME_LIMIT)
    assert AIA_TABLE_SOFT_TIME_LIMIT > AIA_TOOL_SOFT_TIME_LIMIT


def test_the_schedule_keeps_its_longer_window():
    # The schedule spans the whole course, not one set of exercises.
    from src.features.ai_assistant.tasks.studio.schedule import run_generate_schedule
    assert _limits(run_generate_schedule) == (AIA_SCHEDULE_SOFT_TIME_LIMIT,
                                              AIA_SCHEDULE_TIME_LIMIT)


@pytest.mark.parametrize("soft, hard", [
    (AIA_TOOL_SOFT_TIME_LIMIT, AIA_TOOL_TIME_LIMIT),
    (AIA_SCHEDULE_SOFT_TIME_LIMIT, AIA_SCHEDULE_TIME_LIMIT),
])
def test_the_hard_stop_leaves_a_minute_to_fail_cleanly(soft, hard):
    """The hard limit needs headroom, otherwise the cleanup aborts."""
    assert hard - soft >= 60
