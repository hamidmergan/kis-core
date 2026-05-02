"""Basic CRUD operations on the jobs table."""
from ._shared import (
    json, datetime, timedelta, timezone,
    psycopg2, MAX_RESULT_FILES, JOB_RETENTION_HOURS,
    get_connection, _notify_job_update,
)


def create_job(
    job_uuid: str,
    user_id: int,
    tool: str,
    original_filename: str,
    input_path: str | None = None,
    locale: str = "de",
) -> None:
    expires_at = datetime.now(timezone.utc) + timedelta(hours=JOB_RETENTION_HOURS)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO jobs (job_uuid, user_id, tool, original_filename, input_path, expires_at, creator_locale)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (job_uuid, user_id, tool, original_filename, input_path, expires_at, locale),
            )
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
                       WHERE job_uuid = %s AND status != 'awaiting_user'""",
                    (status, error_message, progress_json, now, now, job_uuid),
                )
            elif status in ("success", "failed"):
                cur.execute(
                    """UPDATE jobs
                       SET status = %s, error_message = %s, progress = %s,
                           progress_updated_at = %s, completed_at = %s
                       WHERE job_uuid = %s AND status != 'awaiting_user'""",
                    (status, error_message, progress_json, now, now, job_uuid),
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
                       progress = NULL, progress_updated_at = %s
                   WHERE job_uuid = %s""",
                (now, job_uuid),
            )
        conn.commit()
    _notify_job_update(job_uuid)


def update_job_result(
    job_uuid: str,
    result_path: str,
    result_filename: str,
) -> list[str]:
    """Save job result. Returns job_uuids that exceed MAX_RESULT_FILES and must be evicted.

    Use storage.save_result_and_evict() which fetches user_id via delete_job() before
    deleting the storage folder.
    """
    from ._queries import get_all_results_for_user  # avoid circular import

    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "UPDATE jobs SET result_path = %s, result_filename = %s WHERE job_uuid = %s RETURNING user_id",
                (result_path, result_filename, job_uuid),
            )
            row = cur.fetchone()
            if not row:
                conn.commit()
                return []
            user_id = row["user_id"]
        conn.commit()

    old_jobs = get_all_results_for_user(user_id)
    excess = len(old_jobs) - MAX_RESULT_FILES
    if excess <= 0:
        return []
    return [old_jobs[i]["job_uuid"] for i in range(excess)]
