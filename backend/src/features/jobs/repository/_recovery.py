"""Attempt counting for jobs that resume by themselves, and the supervisor's claim."""
from ._shared import (
    datetime, timedelta, timezone,
    psycopg2, get_connection, _notify_job_update,
)
from ._counts import count_job, messpunkt

# A resumed screencast has to go back through its per-person queue, the others start directly.
_QUEUED_TOOLS = ("screencast_translate", "screencast_render")


def record_failed_attempt(
    job_uuid: str,
    error_message: str,
    *,
    max_resumes: int,
    backoff: tuple[int, ...],
    paused_message: str | None = None,
    stale_before: datetime | None = None,
) -> str | None:
    """Counts one failed attempt and parks the job, returns the new status or None if it did not apply."""
    now = datetime.now(timezone.utc)
    status: str | None = None
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Postgres compares the timestamps, the column is naive and the cutoff is not.
            cur.execute(
                """SELECT status, attempts,
                          (%s::timestamptz IS NULL
                           OR COALESCE(progress_updated_at, created_at) <= %s::timestamptz) AS veraltet
                   FROM jobs WHERE job_uuid = %s FOR UPDATE""",
                (stale_before, stale_before, job_uuid),
            )
            row = cur.fetchone()
            # The watchdog only wins when the job really did not report in the meantime.
            if row and row[0] in ("pending", "running") and row[2]:
                versuche = (row[1] or 0) + 1
                if versuche <= max_resumes:
                    status = "waiting_retry"
                    faellig = now + timedelta(seconds=backoff[min(versuche, len(backoff)) - 1])
                    meldung = error_message
                else:
                    status = "paused"
                    faellig = None
                    meldung = paused_message or error_message
                cur.execute(
                    """UPDATE jobs
                       SET status = %s, attempts = %s, next_attempt_at = %s,
                           error_message = %s, celery_task_id = NULL, progress_updated_at = %s
                       WHERE job_uuid = %s""",
                    (status, versuche, faellig, meldung, now, job_uuid),
                )
        conn.commit()
    if status:
        _notify_job_update(job_uuid)
    return status


def claim_due_retries(limit: int = 20) -> list[dict]:
    """Takes the jobs whose next try is due, atomically, so two ticks cannot take the same one."""
    now = datetime.now(timezone.utc)
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """UPDATE jobs SET
                       status = CASE WHEN tool = ANY(%s) THEN 'queued' ELSE 'pending' END,
                       next_attempt_at = NULL, progress_updated_at = %s
                   WHERE job_uuid IN (
                       SELECT job_uuid FROM jobs
                       WHERE status = 'waiting_retry' AND next_attempt_at <= %s
                       ORDER BY next_attempt_at
                       LIMIT %s
                       FOR UPDATE SKIP LOCKED
                   )
                   RETURNING job_uuid, user_id, tool, progress, attempts,
                             creator_locale, input_path, original_filename, status""",
                (list(_QUEUED_TOOLS), now, now, limit),
            )
            rows = [dict(row) for row in cur.fetchall()]
        conn.commit()
    for row in rows:
        _notify_job_update(row["job_uuid"])
    return rows


def job_claim(job_uuid: str) -> tuple[str, int] | None:
    """Status and attempt count, the pair a running stage checks to know it is still the current one."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT status, attempts FROM jobs WHERE job_uuid = %s", (job_uuid,))
            row = cur.fetchone()
        return (row[0], row[1] or 0) if row else None


def reset_attempts(job_uuid: str) -> None:
    """A person starting the job again gets the full set of automatic tries back."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE jobs SET attempts = 0, next_attempt_at = NULL WHERE job_uuid = %s",
                (job_uuid,),
            )
        conn.commit()


def expire_parked_job(job_uuid: str, error_message: str) -> None:
    """Ends a job nobody came back to, the one path that may fail an awaiting_user row."""
    now = datetime.now(timezone.utc)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT status, tool, started_at, render_started_at FROM jobs
                   WHERE job_uuid = %s FOR UPDATE""",
                (job_uuid,),
            )
            vorher = cur.fetchone()
            cur.execute(
                """UPDATE jobs
                   SET status = 'failed', error_message = %s,
                       completed_at = %s, progress_updated_at = %s, next_attempt_at = NULL
                   WHERE job_uuid = %s AND status IN ('awaiting_user', 'paused')""",
                (error_message, now, now, job_uuid),
            )
            if vorher and cur.rowcount:
                count_job(
                    cur, vorher[1], "failed",
                    messpunkt(vorher[1], vorher[2], vorher[3]), now,
                )
        conn.commit()
    _notify_job_update(job_uuid)


def jobs_in_flight() -> list[dict]:
    """Every job that was mid-run, read once at startup to hand it back to the recovery path."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT job_uuid, user_id, tool, progress, attempts, creator_locale,
                          input_path, original_filename, status
                   FROM jobs WHERE status IN ('pending', 'running')"""
            )
            return [dict(row) for row in cur.fetchall()]
