"""Job data access, split into submodules and re-exported here."""
from ._crud import (
    create_job,
    update_job_expiry,
    set_job_input_path,
    get_job,
    delete_job,
    update_job_status,
    reset_job_to_awaiting,
    update_job_result,
)
from ._queries import (
    get_jobs_by_user,
    count_active_jobs_for_tool,
    has_active_job_for_tool,
    count_all_jobs_for_tool,
    get_next_queued_job,
    count_all_jobs_for_tool_excluding,
    get_all_results_for_user,
    get_all_jobs,
)
from ._retention import (
    select_jobs_to_evict,
    get_jobs_for_user_newest_first,
    get_users_over_cap,
)
from ._lifecycle import (
    set_job_celery_task_id,
    get_job_by_celery_task_id,
    set_generating_scripts_flag,
    transition_job_to_pending,
    transition_job_to_queued,
    claim_job_for_retry,
    reset_stuck_jobs,
    set_render_started_at,
    set_render_queued_at,
    touch_job_heartbeat,
    get_stale_awaiting_user_jobs,
    get_stuck_running_jobs,
)
from ._counts import get_counts
from ._stats import (
    get_job_stats,
    get_job_activity_log,
)

__all__ = [
    # crud
    "create_job", "update_job_expiry", "set_job_input_path", "get_job",
    "delete_job", "update_job_status", "reset_job_to_awaiting", "update_job_result",
    # queries
    "get_jobs_by_user", "count_active_jobs_for_tool", "has_active_job_for_tool",
    "count_all_jobs_for_tool", "get_next_queued_job", "count_all_jobs_for_tool_excluding",
    "get_all_results_for_user", "get_all_jobs",
    # retention
    "select_jobs_to_evict", "get_jobs_for_user_newest_first", "get_users_over_cap",
    # lifecycle
    "set_job_celery_task_id", "get_job_by_celery_task_id", "set_generating_scripts_flag",
    "transition_job_to_pending", "transition_job_to_queued", "claim_job_for_retry",
    "reset_stuck_jobs", "set_render_started_at", "set_render_queued_at",
    "touch_job_heartbeat", "get_stale_awaiting_user_jobs", "get_stuck_running_jobs",
    # stats
    "get_job_stats", "get_job_activity_log", "get_counts",
]
