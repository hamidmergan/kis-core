"""Retention: the last N jobs per user are kept."""
from ._shared import psycopg2, get_connection

# Running jobs are never cleared, hanging ones are caught by the watchdog.
ACTIVE_STATUSES = ("pending", "queued", "running", "awaiting_user", "waiting_retry", "paused")
# Pages may be shared, so they have their own limit and never drop out of the pool.
OUTSIDE_POOL = ("pages",)


def select_jobs_to_evict(
    jobs_newest_first: list[dict],
    cap: int | None = None,
) -> list[dict]:
    """Which jobs drop out of the pool, running ones never."""
    if cap is None:
        from src.services.tool_limits import results_kept_per_user
        cap = results_kept_per_user()
    if cap < 0:
        return []
    return [job for job in jobs_newest_first[cap:] if job["status"] not in ACTIVE_STATUSES]


def get_jobs_for_user_newest_first(user_id: int) -> list[dict]:
    """All jobs of a user, newest first, the basis of every cleanup."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT job_uuid, user_id, status, original_filename, result_filename
                   FROM jobs WHERE user_id = %s AND tool <> ALL(%s)
                   ORDER BY created_at DESC""",
                (user_id, list(OUTSIDE_POOL)),
            )
            return [dict(row) for row in cur.fetchall()]


def get_users_over_cap(cap: int | None = None) -> list[int]:
    """Users with more jobs than allowed, for the nightly cleanup."""
    if cap is None:
        from src.services.tool_limits import results_kept_per_user
        cap = results_kept_per_user()
    if cap < 0:
        return []
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT user_id FROM jobs WHERE tool <> ALL(%s) GROUP BY user_id HAVING COUNT(*) > %s",
                (list(OUTSIDE_POOL), cap),
            )
            return [row[0] for row in cur.fetchall()]
