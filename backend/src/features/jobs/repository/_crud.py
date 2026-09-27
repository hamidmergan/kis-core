"""Basic CRUD operations on the jobs table."""
from ._shared import (
    json, datetime, timedelta, timezone,
    psycopg2, get_connection, _notify_job_update,
)
from ._counts import count_job, count_started, messpunkt
from ._queries import VOICE_TOOLS

# Namespace of the per-person advisory lock, so it never collides with other locks.
_OPEN_JOBS_LOCK = 7301


class TooManyOpenJobs(RuntimeError):
    """The person already has as many working jobs as the limit allows."""


def create_job(
    job_uuid: str,
    user_id: int,
    tool: str,
    original_filename: str,
    input_path: str | None = None,
    locale: str = "de",
    limit: int | None = None,
) -> None:
    # No expiry date, retention is governed by the pool alone (see _retention.py).
    with get_connection() as conn:
        with conn.cursor() as cur:
            if limit is not None and limit >= 0:
                # Two tabs of one person wait here for each other, so both cannot count below the limit.
                cur.execute("SELECT pg_advisory_xact_lock(%s, %s)", (_OPEN_JOBS_LOCK, user_id))
                # Only jobs of the same kind count, with a voice or without one.
                cur.execute(
                    """SELECT COUNT(*) FROM jobs
                       WHERE user_id = %s AND status IN ('pending', 'running', 'queued', 'waiting_retry')
                       AND (tool = ANY(%s)) = %s""",
                    (user_id, sorted(VOICE_TOOLS), tool in VOICE_TOOLS),
                )
                if cur.fetchone()[0] >= limit:
                    conn.rollback()
                    raise TooManyOpenJobs()
            cur.execute(
                """
                INSERT INTO jobs (job_uuid, user_id, tool, original_filename, input_path, creator_locale)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (job_uuid, user_id, tool, original_filename, input_path, locale),
            )
            count_started(cur, tool)
        conn.commit()


def update_job_expiry(job_uuid: str, hours: int) -> None:
    """Extend (or set) the expires_at for a job to now + hours."""
    new_expiry = datetime.now(timezone.utc) + timedelta(hours=hours)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE jobs SET expires_at = %s WHERE job_uuid = %s",
                (new_expiry, job_uuid),
            )
        conn.commit()


def set_job_input_path(job_uuid: str, input_path: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE jobs SET input_path = %s WHERE job_uuid = %s",
                (input_path, job_uuid),
            )
        conn.commit()


def get_job(job_uuid: str):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM jobs WHERE job_uuid = %s", (job_uuid,))
            return cur.fetchone()


def delete_job(job_uuid: str) -> dict | None:
    """Delete a job record and return its user_id + file paths for cleanup."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT user_id, input_path, result_path, celery_task_id FROM jobs WHERE job_uuid = %s",
                (job_uuid,),
            )
            row = cur.fetchone()
            if not row:
                return None
            cur.execute("DELETE FROM jobs WHERE job_uuid = %s", (job_uuid,))
        conn.commit()
        return dict(row)


def update_job_status(
    job_uuid: str,
    status: str,
    error_message: str | None = None,
    progress: dict | None = None,
) -> None:
    progress_json = json.dumps(progress) if progress is not None else None
    now = datetime.now(timezone.utc)
    with get_connection() as conn:
        with conn.cursor() as cur:
            if status == "running":
                cur.execute(
                    """UPDATE jobs
                       SET status = %s, error_message = %s, progress = %s,
                           progress_updated_at = %s,
                           started_at = COALESCE(started_at, %s)
                       WHERE job_uuid = %s AND status IN ('pending', 'running')""",
                    (status, error_message, progress_json, now, now, job_uuid),
                )
            elif status in ("success", "failed"):
                # Lock first and read the old state, otherwise a second call counts twice.
                cur.execute(
                    """SELECT status, tool, started_at, render_started_at
                       FROM jobs WHERE job_uuid = %s FOR UPDATE""",
                    (job_uuid,),
                )
                vorher = cur.fetchone()
                cur.execute(
                    """UPDATE jobs
                       SET status = %s, error_message = %s, progress = %s,
                           progress_updated_at = %s, completed_at = %s,
                           attempts = 0, next_attempt_at = NULL
                       WHERE job_uuid = %s AND status != 'awaiting_user'""",
                    (status, error_message, progress_json, now, now, job_uuid),
                )
                if vorher and cur.rowcount and vorher[0] not in ("success", "failed"):
                    count_job(
                        cur, vorher[1], status,
                        messpunkt(vorher[1], vorher[2], vorher[3]), now,
                    )
            else:
                cur.execute(
                    """UPDATE jobs
                       SET status = %s, error_message = %s, progress = %s,
                           progress_updated_at = %s
                       WHERE job_uuid = %s""",
                    (status, error_message, progress_json, now, job_uuid),
                )
        conn.commit()
    if status in ("success", "failed", "awaiting_user", "pending", "queued", "running"):
        _notify_job_update(job_uuid)


def reset_job_to_awaiting(job_uuid: str) -> None:
    """Stop a running render: set status back to awaiting_user, clear task ID and progress."""
    now = datetime.now(timezone.utc)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE jobs
                   SET status = 'awaiting_user', celery_task_id = NULL,
                       progress = NULL, progress_updated_at = %s,
                       attempts = 0, next_attempt_at = NULL
                   WHERE job_uuid = %s""",
                (now, job_uuid),
            )
        conn.commit()
    _notify_job_update(job_uuid)


def update_job_result(
    job_uuid: str,
    result_path: str,
    result_filename: str,
) -> None:
    """Stores the result, the clearing lives in _retention.py."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE jobs SET result_path = %s, result_filename = %s WHERE job_uuid = %s",
                (result_path, result_filename, job_uuid),
            )
        conn.commit()
