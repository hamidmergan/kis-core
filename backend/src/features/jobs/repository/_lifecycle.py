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
    """Sets or clears the marker that texts are being generated right now."""
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
    """Safely sets a job to 'pending', True only for the winner."""
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
    """Moves a job the person restarts to 'running', with a fresh set of automatic tries."""
    now = datetime.now(timezone.utc)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE jobs SET status = 'running', progress_updated_at = %s, error_message = NULL,
                       attempts = 0, next_attempt_at = NULL
                   WHERE job_uuid = %s AND status IN ('failed', 'paused')""",
                (now, job_uuid),
            )
            affected = cur.rowcount
        conn.commit()
        return affected == 1


def set_render_started_at(job_uuid: str) -> None:
    """Sets render_started_at once (COALESCE, not overwritten on a retry)."""
    now = datetime.now(timezone.utc)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE jobs SET render_started_at = COALESCE(render_started_at, %s) WHERE job_uuid = %s",
                (now, job_uuid),
            )
        conn.commit()


def set_render_queued_at(job_uuid: str) -> None:
    """Sets render_queued_at once, when the render job enters the Celery queue."""
    now = datetime.now(timezone.utc)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE jobs SET render_queued_at = COALESCE(render_queued_at, %s) WHERE job_uuid = %s",
                (now, job_uuid),
            )
        conn.commit()


def touch_job_heartbeat(job_uuid: str) -> None:
    """Refreshes the progress heartbeat so the watchdog does not strike."""
    now = datetime.now(timezone.utc)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE jobs SET progress_updated_at = %s WHERE job_uuid = %s AND status = 'running'",
                (now, job_uuid),
            )
        conn.commit()


def get_stale_awaiting_user_jobs(threshold_hours: int = 2) -> list[dict]:
    """Return parked jobs idle for longer than threshold_hours (user never came back)."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=threshold_hours)
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT job_uuid, tool, creator_locale FROM jobs
                   WHERE status IN ('awaiting_user', 'paused')
                   AND COALESCE(progress_updated_at, created_at) <= %s""",
                (cutoff,),
            )
            rows = cur.fetchall()
        return [dict(row) for row in rows]


def get_stuck_running_jobs(threshold_minutes: int) -> list[dict]:
    """Return running/pending jobs that have not made progress for longer than threshold_minutes."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=threshold_minutes)
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT job_uuid, user_id, tool, status, progress, progress_updated_at,
                          creator_locale, celery_task_id FROM jobs
                   WHERE status IN ('pending', 'running')
                   AND COALESCE(progress_updated_at, created_at) <= %s""",
                (cutoff,),
            )
            rows = cur.fetchall()
        return [dict(row) for row in rows]
