"""Job state transitions, retry claiming, stuck detection, Celery task linking."""
from ._shared import (
    json, datetime, timedelta, timezone,
    psycopg2, get_connection, _notify_job_update,
)


def set_job_celery_task_id(job_uuid: str, celery_task_id: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE jobs SET celery_task_id = %s WHERE job_uuid = %s",
                (celery_task_id, job_uuid),
            )
        conn.commit()


def get_job_by_celery_task_id(celery_task_id: str) -> dict | None:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT * FROM jobs WHERE celery_task_id = %s AND status = 'running'",
                (celery_task_id,),
            )
            row = cur.fetchone()
        return dict(row) if row else None


def set_generating_scripts_flag(job_uuid: str, generating: bool) -> None:
    """Merge or remove the 'generating_scripts' marker in the job's progress JSON.

    Used to signal My Jobs that the resume button should be hidden while
    script generation is in progress.
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT progress FROM jobs WHERE job_uuid = %s", (job_uuid,))
            row = cur.fetchone()
            if row is None:
                return
            try:
                progress = json.loads(row[0] or "{}")
            except Exception:
                progress = {}
            if generating:
                progress["generating_scripts"] = True
            else:
                progress.pop("generating_scripts", None)
            cur.execute(
                "UPDATE jobs SET progress = %s WHERE job_uuid = %s",
                (json.dumps(progress), job_uuid),
            )
        conn.commit()
    _notify_job_update(job_uuid)


def transition_job_to_pending(
    job_uuid: str,
    user_id: int,
    from_statuses: tuple = ("awaiting_user",),
) -> bool:
    """Atomically transition a job to 'pending' from one of the allowed source statuses.

    Uses SELECT FOR UPDATE to prevent race conditions when multiple tabs
    submit the same job simultaneously.

    Returns True if the transition succeeded (this caller owns the job),
    False if another request already transitioned it (status not in from_statuses).
    """
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT status FROM jobs
                   WHERE job_uuid = %s AND user_id = %s
                   FOR UPDATE""",
                (job_uuid, user_id),
            )
            row = cur.fetchone()
            if row is None or row[0] not in from_statuses:
                conn.rollback()
                return False
            cur.execute(
                "UPDATE jobs SET status = 'pending' WHERE job_uuid = %s",
                (job_uuid,),
            )
        conn.commit()
    return True


def transition_job_to_queued(
    job_uuid: str,
    user_id: int,
    from_statuses: tuple = ("awaiting_user", "failed", "success"),
) -> bool:
    """Atomically transition a job to 'queued' from one of the allowed source statuses."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT status FROM jobs
                   WHERE job_uuid = %s AND user_id = %s
                   FOR UPDATE""",
                (job_uuid, user_id),
            )
            row = cur.fetchone()
            if row is None or row[0] not in from_statuses:
                conn.rollback()
                return False
            cur.execute(
                "UPDATE jobs SET status = 'queued', error_message = NULL WHERE job_uuid = %s",
                (job_uuid,),
            )
        conn.commit()
    _notify_job_update(job_uuid)
    return True


def claim_job_for_retry(job_uuid: str) -> bool:
    """Atomically set job status from 'failed' to 'running' for retry.
    Returns True if successful, False if job was not in 'failed' state (race condition)."""
    now = datetime.now(timezone.utc)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE jobs SET status = 'running', progress_updated_at = %s, error_message = NULL
                   WHERE job_uuid = %s AND status = 'failed'""",
                (now, job_uuid),
            )
            affected = cur.rowcount
        conn.commit()
        return affected == 1


def reset_stuck_jobs() -> int:
    """Mark all pending/running jobs as failed on server startup.

    Called once when the backend starts. Jobs stuck in 'pending' or 'running'
    mean the server crashed mid-task and the Celery broker lost the message.
    They can be manually retried via the retry endpoint.
    Returns the number of jobs reset.
    """
    now = datetime.now(timezone.utc)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE jobs
                   SET status = 'failed',
                       error_message = 'Server wurde neugestartet - bitte Wiederholen klicken.',
                       completed_at = %s
                   WHERE status IN ('pending', 'running')""",
                (now,),
            )
            affected = cur.rowcount
        conn.commit()
        return affected


def set_render_started_at(job_uuid: str) -> None:
    """Setzt render_started_at einmalig (COALESCE - nicht überschreiben bei Retry)."""
    now = datetime.now(timezone.utc)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE jobs SET render_started_at = COALESCE(render_started_at, %s) WHERE job_uuid = %s",
                (now, job_uuid),
            )
        conn.commit()


def set_render_queued_at(job_uuid: str) -> None:
    """Setzt render_queued_at einmalig - Zeitpunkt wenn Render-Job in Celery Queue eingereiht wird."""
    now = datetime.now(timezone.utc)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE jobs SET render_queued_at = COALESCE(render_queued_at, %s) WHERE job_uuid = %s",
                (now, job_uuid),
            )
        conn.commit()


def touch_job_heartbeat(job_uuid: str) -> None:
    """Update progress_updated_at without touching any other field.
    Called periodically during long external API calls to prevent the watchdog
    from falsely marking an actively-running job as stuck.
    Only updates if the job is still in 'running' state.
    """
    now = datetime.now(timezone.utc)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE jobs SET progress_updated_at = %s WHERE job_uuid = %s AND status = 'running'",
                (now, job_uuid),
            )
        conn.commit()


def get_stale_awaiting_user_jobs(threshold_hours: int = 2) -> list[dict]:
    """Return awaiting_user jobs older than threshold_hours (user never came back to resume)."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=threshold_hours)
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT job_uuid, tool, creator_locale FROM jobs WHERE status = 'awaiting_user' AND created_at <= %s",
                (cutoff,),
            )
            rows = cur.fetchall()
        return [dict(row) for row in rows]


def get_stuck_running_jobs(threshold_minutes: int = 20) -> list[dict]:
    """Return running/pending jobs that have not made progress for longer than threshold_minutes."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=threshold_minutes)
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT job_uuid, tool, progress, progress_updated_at, creator_locale FROM jobs
                   WHERE (
                       (status = 'running' AND progress_updated_at IS NOT NULL AND progress_updated_at <= %s)
                       OR
                       (status = 'running' AND progress_updated_at IS NULL AND created_at <= %s)
                       OR
                       (status = 'pending' AND created_at <= %s)
                   )""",
                (cutoff, cutoff, cutoff),
            )
            rows = cur.fetchall()
        return [dict(row) for row in rows]
