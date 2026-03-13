import json
import os
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

import psycopg2
import psycopg2.extras
import psycopg2.pool

_REDIS_URL = os.environ.get("REDIS_URL", "redis://kis-redis:6379/0")


def _notify_job_update(job_uuid: str) -> None:
    """Publish to Redis so SSE clients receive a real-time update."""
    try:
        import redis as _redis
        r = _redis.from_url(_REDIS_URL, socket_connect_timeout=1, socket_timeout=1)
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT user_id FROM jobs WHERE job_uuid = %s", (job_uuid,))
                row = cur.fetchone()
        if row:
            r.publish(f"jobs:{row[0]}", "update")
        r.close()
    except Exception:
        pass

_TZ_BERLIN = ZoneInfo("Europe/Berlin")

from src.limits import MAX_RESULT_FILES, JOB_RETENTION_HOURS  # noqa: E402

_pool: psycopg2.pool.ThreadedConnectionPool | None = None


def _de_date_to_utc(date_str: str, end_of_day: bool = False) -> str:
    """Convert a YYYY-MM-DD German local date to a UTC datetime string for DB comparison.

    DB timestamps are stored in UTC. The user picks a date in German local time,
    so 'date_to=2026-02-26' means up to 2026-02-26 23:59:59 Europe/Berlin,
    which is 2026-02-26 22:59:59 UTC in winter (UTC+1).
    """
    year, month, day = int(date_str[:4]), int(date_str[5:7]), int(date_str[8:10])
    hour, minute, second = (23, 59, 59) if end_of_day else (0, 0, 0)
    local_dt = datetime(year, month, day, hour, minute, second, tzinfo=_TZ_BERLIN)
    return local_dt.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None:
        dsn = os.environ["DATABASE_URL"]
        _pool = psycopg2.pool.ThreadedConnectionPool(1, 20, dsn)
    return _pool


@contextmanager
def get_connection():
    pool = _get_pool()
    conn = pool.getconn()
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def init_db(admin_email: Optional[str] = None) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id            SERIAL PRIMARY KEY,
                    ldap_username TEXT NOT NULL UNIQUE,
                    display_name  TEXT NOT NULL,
                    email         TEXT,
                    active        INTEGER NOT NULL DEFAULT 1,
                    created_at    TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS whitelist (
                    id         SERIAL PRIMARY KEY,
                    email      TEXT NOT NULL UNIQUE,
                    created_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id                  SERIAL PRIMARY KEY,
                    job_uuid            TEXT NOT NULL UNIQUE,
                    user_id             INTEGER NOT NULL DEFAULT 0,
                    tool                TEXT NOT NULL,
                    original_filename   TEXT NOT NULL DEFAULT '',
                    input_path          TEXT,
                    result_path         TEXT,
                    result_filename     TEXT,
                    status              TEXT NOT NULL DEFAULT 'pending',
                    error_message       TEXT,
                    progress            TEXT,
                    celery_task_id      TEXT,
                    created_at          TIMESTAMP NOT NULL DEFAULT NOW(),
                    started_at          TIMESTAMP,
                    completed_at        TIMESTAMP,
                    expires_at          TIMESTAMP,
                    progress_updated_at TIMESTAMP,
                    render_started_at   TIMESTAMP,
                    render_queued_at    TIMESTAMP
                )
            """)
            cur.execute("ALTER TABLE jobs ADD COLUMN IF NOT EXISTS render_queued_at TIMESTAMP")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    id         SERIAL PRIMARY KEY,
                    key        TEXT NOT NULL UNIQUE,
                    value      TEXT NOT NULL,
                    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_quotas (
                    id                SERIAL PRIMARY KEY,
                    user_id           INTEGER NOT NULL,
                    quota_type        TEXT NOT NULL,
                    used              INTEGER NOT NULL DEFAULT 0,
                    window_started_at TIMESTAMP,
                    reset_at          TIMESTAMP,
                    updated_at        TIMESTAMP NOT NULL DEFAULT NOW(),
                    UNIQUE (user_id, quota_type)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_quota_overrides (
                    id          SERIAL PRIMARY KEY,
                    user_id     INTEGER NOT NULL,
                    quota_type  TEXT NOT NULL,
                    limit_value INTEGER NOT NULL,
                    updated_at  TIMESTAMP NOT NULL DEFAULT NOW(),
                    UNIQUE (user_id, quota_type)
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS user_quota_resets (
                    user_id  INTEGER PRIMARY KEY,
                    reset_at TIMESTAMP NOT NULL
                )
            """)
            if admin_email and admin_email.strip():
                cur.execute(
                    "INSERT INTO whitelist (email) VALUES (%s) ON CONFLICT DO NOTHING",
                    (admin_email.strip().lower(),),
                )
        conn.commit()


# --- Users ---

def get_user_by_username(ldap_username: str):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE ldap_username = %s", (ldap_username,))
            return cur.fetchone()


def get_user_by_id(user_id: int):
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
            return cur.fetchone()


def create_user(ldap_username: str, display_name: str, email: str, active: int) -> int:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO users (ldap_username, display_name, email, active) VALUES (%s, %s, %s, %s) RETURNING id",
                (ldap_username, display_name, email, active),
            )
            user_id = cur.fetchone()[0]
        conn.commit()
        return user_id


def update_user(user_id: int, display_name: str, email: str, active: int) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET display_name = %s, email = %s, active = %s WHERE id = %s",
                (display_name, email, active, user_id),
            )
        conn.commit()


# --- Whitelist ---

def get_whitelist_emails() -> list[str]:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT email FROM whitelist ORDER BY created_at")
            rows = cur.fetchall()
        return [row["email"] for row in rows]


def add_to_whitelist(email: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO whitelist (email) VALUES (%s) ON CONFLICT DO NOTHING",
                (email.strip().lower(),),
            )
        conn.commit()


def remove_from_whitelist(email: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM whitelist WHERE LOWER(email) = LOWER(%s)", (email.strip(),))
        conn.commit()


def is_email_whitelisted(email: str) -> bool:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT 1 FROM whitelist WHERE LOWER(email) = LOWER(%s)", (email.strip(),)
            )
            return cur.fetchone() is not None


# --- Settings (key/value store) ---

def get_setting(key: str, default: str = "") -> str:
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT value FROM settings WHERE key = %s", (key,))
            row = cur.fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO settings (key, value)
                   VALUES (%s, %s)
                   ON CONFLICT (key) DO UPDATE
                   SET value = EXCLUDED.value,
                       updated_at = NOW()""",
                (key, value),
            )
        conn.commit()


# --- Jobs ---

def create_job(
    job_uuid: str,
    user_id: int,
    tool: str,
    original_filename: str,
    input_path: str | None = None,
) -> None:
    expires_at = datetime.now(timezone.utc) + timedelta(hours=JOB_RETENTION_HOURS)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO jobs (job_uuid, user_id, tool, original_filename, input_path, expires_at)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (job_uuid, user_id, tool, original_filename, input_path, expires_at),
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


def get_jobs_by_user(
    user_id: int, limit: int = 20, offset: int = 0, q: str = "",
    date_from: str = "", date_to: str = "",
    extra_tools: list[str] | None = None,
) -> tuple[list[dict], int]:
    conditions = ["user_id = %s", "(expires_at IS NULL OR expires_at > NOW())"]
    params: list = [user_id]
    if q:
        like = f"%{q}%"
        if extra_tools:
            conditions.append("(original_filename ILIKE %s OR tool ILIKE %s OR tool = ANY(%s))")
            params += [like, like, extra_tools]
        else:
            conditions.append("(original_filename ILIKE %s OR tool ILIKE %s)")
            params += [like, like]
    if date_from:
        conditions.append("created_at::date >= %s::date")
        params.append(date_from)
    if date_to:
        conditions.append("created_at::date <= %s::date")
        params.append(date_to)
    where = " AND ".join(conditions)
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(f"SELECT COUNT(*) AS total FROM jobs WHERE {where}", params)
            total = cur.fetchone()["total"]
            cur.execute(
                f"SELECT * FROM jobs WHERE {where} ORDER BY created_at DESC LIMIT %s OFFSET %s",
                params + [limit, offset],
            )
            rows = cur.fetchall()
    return [dict(row) for row in rows], total


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


def delete_job(job_uuid: str) -> dict | None:
    """Delete a job record and return its file paths for cleanup."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                "SELECT input_path, result_path, celery_task_id FROM jobs WHERE job_uuid = %s",
                (job_uuid,),
            )
            row = cur.fetchone()
            if not row:
                return None
            cur.execute("DELETE FROM jobs WHERE job_uuid = %s", (job_uuid,))
        conn.commit()
        return dict(row)


def count_active_jobs_for_tool(user_id: int, tools: list[str]) -> int:
    """Return the number of pending/running/awaiting_user jobs the user has for any of the given tools."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT COUNT(*) FROM jobs
                   WHERE user_id = %s AND tool = ANY(%s)
                   AND status IN ('pending', 'running', 'awaiting_user')""",
                (user_id, tools),
            )
            row = cur.fetchone()
            return row[0] if row else 0


def has_active_job_for_tool(user_id: int, tools: list[str]) -> bool:
    """Return True if the user has a pending/running/awaiting_user job for any of the given tools."""
    return count_active_jobs_for_tool(user_id, tools) > 0


def count_all_jobs_for_tool(user_id: int, tools: list[str]) -> int:
    """Return total non-terminal jobs (pending/running/awaiting_user/queued) for quota/queue-size checks."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT COUNT(*) FROM jobs
                   WHERE user_id = %s AND tool = ANY(%s)
                   AND status IN ('pending', 'running', 'awaiting_user', 'queued')""",
                (user_id, tools),
            )
            row = cur.fetchone()
            return row[0] if row else 0


def get_next_queued_job(user_id: int, tools: list[str]) -> dict | None:
    """Atomically claim the oldest queued job by transitioning queued → pending,
    but only if the user has no currently active (pending/running) job.
    awaiting_user does NOT block dispatch — it uses no Celery slot.
    Returns the updated job row, or None if no queued job exists or user is already active."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """UPDATE jobs SET status = 'pending'
                   WHERE job_uuid = (
                       SELECT j.job_uuid FROM jobs j
                       WHERE j.user_id = %s AND j.tool = ANY(%s) AND j.status = 'queued'
                       AND NOT EXISTS (
                           SELECT 1 FROM jobs a
                           WHERE a.user_id = %s AND a.tool = ANY(%s)
                           AND a.status IN ('pending', 'running')
                       )
                       ORDER BY j.created_at ASC
                       LIMIT 1
                       FOR UPDATE SKIP LOCKED
                   )
                   RETURNING *""",
                (user_id, tools, user_id, tools),
            )
            conn.commit()
            row = cur.fetchone()
            result = dict(row) if row else None
    if result:
        _notify_job_update(result["job_uuid"])
    return result


def count_all_jobs_for_tool_excluding(user_id: int, tools: list[str], exclude_uuid: str) -> int:
    """Count active/queued jobs (pending/running/awaiting_user/queued) excluding a specific job."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT COUNT(*) FROM jobs
                   WHERE user_id = %s AND tool = ANY(%s)
                   AND status IN ('pending', 'running', 'awaiting_user', 'queued')
                   AND job_uuid != %s""",
                (user_id, tools, exclude_uuid),
            )
            row = cur.fetchone()
            return row[0] if row else 0


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


def get_all_results_for_user(user_id: int) -> list[dict]:
    """Return all jobs with a result_path for the given user, ordered oldest first."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT id, job_uuid, result_path, result_filename, original_filename FROM jobs
                   WHERE user_id = %s AND result_path IS NOT NULL AND status != 'failed'
                   ORDER BY created_at ASC""",
                (user_id,),
            )
            rows = cur.fetchall()
        return [dict(row) for row in rows]


def get_all_users(
    limit: int = 50, offset: int = 0, q: str = "",
    date_from: str = "", date_to: str = "",
) -> tuple[list[dict], int]:
    """All users, newest first. Returns (users, total_count).

    Filters: q (name/username/email), date_from/date_to (YYYY-MM-DD).
    """
    conditions = []
    params: list = []

    if q:
        like = f"%{q}%"
        conditions.append("(display_name ILIKE %s OR ldap_username ILIKE %s OR email ILIKE %s)")
        params += [like, like, like]
    if date_from:
        conditions.append("created_at >= %s::timestamp")
        params.append(_de_date_to_utc(date_from))
    if date_to:
        conditions.append("created_at <= %s::timestamp")
        params.append(_de_date_to_utc(date_to, end_of_day=True))

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                f"SELECT * FROM users {where} ORDER BY created_at DESC LIMIT %s OFFSET %s",
                params + [limit, offset],
            )
            rows = cur.fetchall()
            cur.execute(f"SELECT COUNT(*) AS total FROM users {where}", params)
            total = cur.fetchone()["total"]
    return [dict(row) for row in rows], total


def get_pending_users() -> list[dict]:
    """Users with active=0 (passed LDAP auth but not yet whitelisted)."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute("SELECT * FROM users WHERE active = 0 ORDER BY created_at DESC")
            rows = cur.fetchall()
        return [dict(row) for row in rows]


def activate_user(user_id: int) -> None:
    """Set active=1 for the given user."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE users SET active = 1 WHERE id = %s", (user_id,))
        conn.commit()


def deactivate_user_by_email(email: str) -> None:
    """Set active=0 for any user with the given email."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE users SET active = 0 WHERE LOWER(email) = LOWER(%s)", (email.strip(),)
            )
        conn.commit()


def get_all_jobs(
    limit: int = 50, offset: int = 0, q: str = "",
    date_from: str = "", date_to: str = "",
    extra_tools: list[str] | None = None,
) -> tuple[list[dict], int]:
    """All jobs across all users, with display_name via JOIN, newest first.

    Returns (jobs, total_count).
    Filters: q (user/tool/filename), date_from/date_to (YYYY-MM-DD).
    """
    conditions = ["(j.expires_at IS NULL OR j.expires_at > NOW())"]
    params: list = []

    if q:
        like = f"%{q}%"
        if extra_tools:
            conditions.append(
                "(u.display_name ILIKE %s OR u.ldap_username ILIKE %s OR j.tool ILIKE %s OR j.original_filename ILIKE %s OR j.tool = ANY(%s))"
            )
            params += [like, like, like, like, extra_tools]
        else:
            conditions.append(
                "(u.display_name ILIKE %s OR u.ldap_username ILIKE %s OR j.tool ILIKE %s OR j.original_filename ILIKE %s)"
            )
            params += [like, like, like, like]
    if date_from:
        conditions.append("j.created_at >= %s::timestamp")
        params.append(_de_date_to_utc(date_from))
    if date_to:
        conditions.append("j.created_at <= %s::timestamp")
        params.append(_de_date_to_utc(date_to, end_of_day=True))

    where = "WHERE " + " AND ".join(conditions)

    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                f"""SELECT j.*, u.display_name AS user_display_name, u.ldap_username
                   FROM jobs j
                   LEFT JOIN users u ON j.user_id = u.id
                   {where}
                   ORDER BY j.created_at DESC
                   LIMIT %s OFFSET %s""",
                params + [limit, offset],
            )
            rows = cur.fetchall()
            cur.execute(
                f"""SELECT COUNT(*) AS total FROM jobs j
                   LEFT JOIN users u ON j.user_id = u.id
                   {where}""",
                params,
            )
            total = cur.fetchone()["total"]
    return [dict(row) for row in rows], total


def get_pending_dubbing_jobs() -> list[dict]:
    """Return all running dubbing jobs waiting for ElevenLabs (step='dubbing')."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT job_uuid, progress FROM jobs
                   WHERE tool = 'video_dubbing'
                   AND status = 'running'
                   AND progress LIKE %s""",
                ('%"step": "dubbing"%',),
            )
            rows = cur.fetchall()
        return [dict(row) for row in rows]


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


def set_render_started_at(job_uuid: str) -> None:
    """Setzt render_started_at einmalig (COALESCE — nicht überschreiben bei Retry)."""
    now = datetime.now(timezone.utc)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE jobs SET render_started_at = COALESCE(render_started_at, %s) WHERE job_uuid = %s",
                (now, job_uuid),
            )
        conn.commit()


def set_render_queued_at(job_uuid: str) -> None:
    """Setzt render_queued_at einmalig — Zeitpunkt wenn Render-Job in Celery Queue eingereiht wird."""
    now = datetime.now(timezone.utc)
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE jobs SET render_queued_at = COALESCE(render_queued_at, %s) WHERE job_uuid = %s",
                (now, job_uuid),
            )
        conn.commit()


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
                       error_message = 'Server wurde neugestartet — bitte Wiederholen klicken.',
                       completed_at = %s
                   WHERE status IN ('pending', 'running')""",
                (now,),
            )
            affected = cur.rowcount
        conn.commit()
        return affected


def update_job_result(
    job_uuid: str,
    result_path: str,
    result_filename: str,
) -> list[str]:
    """Save job result. Returns job_uuids that exceed MAX_RESULT_FILES and must be evicted.

    Callers must delete each returned UUID from storage BEFORE calling delete_job()
    so that _job_folder_name() can still resolve the folder name from the DB.
    Use storage.save_result_and_evict() which handles this automatically.
    """
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
                "SELECT job_uuid, tool FROM jobs WHERE status = 'awaiting_user' AND created_at <= %s",
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
                """SELECT job_uuid, tool, progress, progress_updated_at FROM jobs
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


# --- Quota ---

def quota_get_override(user_id: int, quota_type: str) -> Optional[int]:
    """Return per-user override limit, or None if no override exists."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT limit_value FROM user_quota_overrides WHERE user_id = %s AND quota_type = %s",
                (user_id, quota_type),
            )
            row = cur.fetchone()
    return row[0] if row else None


def quota_set_override(user_id: int, quota_type: str, limit_value: int) -> None:
    """Upsert a per-user override. limit_value=-1 means unlimited."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO user_quota_overrides (user_id, quota_type, limit_value)
                   VALUES (%s, %s, %s)
                   ON CONFLICT (user_id, quota_type)
                   DO UPDATE SET limit_value = EXCLUDED.limit_value, updated_at = NOW()""",
                (user_id, quota_type, limit_value),
            )
        conn.commit()


def quota_remove_override(user_id: int, quota_type: str) -> None:
    """Remove a per-user override so the user falls back to the global default."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "DELETE FROM user_quota_overrides WHERE user_id = %s AND quota_type = %s",
                (user_id, quota_type),
            )
        conn.commit()


def quota_reset(user_id: int, quota_type: str) -> None:
    """Admin: immediately zero a user's quota counter and clear the global reset timer."""
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """UPDATE user_quotas
                   SET used = 0, window_started_at = NULL, reset_at = NULL, updated_at = NOW()
                   WHERE user_id = %s AND quota_type = %s""",
                (user_id, quota_type),
            )
            cur.execute(
                "DELETE FROM user_quota_resets WHERE user_id = %s",
                (user_id,),
            )
        conn.commit()


def quota_get_all_for_user(user_id: int) -> tuple[list[dict], Optional[datetime]]:
    """Return all quota rows for a user (used, reset_at, override if any) plus the global reset_at."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT
                     COALESCE(q.quota_type, o.quota_type) AS quota_type,
                     COALESCE(q.used, 0)                  AS used,
                     q.reset_at,
                     o.limit_value                        AS override
                   FROM user_quotas q
                   FULL OUTER JOIN user_quota_overrides o
                     ON o.user_id = q.user_id AND o.quota_type = q.quota_type
                   WHERE COALESCE(q.user_id, o.user_id) = %s""",
                (user_id,),
            )
            rows = cur.fetchall()
            cur.execute(
                "SELECT reset_at FROM user_quota_resets WHERE user_id = %s",
                (user_id,),
            )
            gr = cur.fetchone()
            global_reset_at: Optional[datetime] = gr["reset_at"] if gr else None
    return [dict(row) for row in rows], global_reset_at


def quota_get_all_users_usage() -> list[dict]:
    """Admin: return all active users with quota data (used=0 if no activity yet)."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT u.id AS user_id, u.ldap_username, u.display_name,
                          q.quota_type, COALESCE(q.used, 0) AS used, q.reset_at,
                          o.limit_value AS override
                   FROM users u
                   LEFT JOIN user_quotas q ON q.user_id = u.id
                   LEFT JOIN user_quota_overrides o
                     ON o.user_id = u.id AND o.quota_type = q.quota_type
                   WHERE u.active = 1
                   ORDER BY u.display_name, q.quota_type"""
            )
            rows = cur.fetchall()
            cur.execute("SELECT user_id, reset_at FROM user_quota_resets")
            global_resets = cur.fetchall()
    result = [dict(row) for row in rows]
    resets_by_uid = {gr["user_id"]: gr["reset_at"] for gr in global_resets}
    for row in result:
        uid = row["user_id"]
        gr_at = resets_by_uid.get(uid)
        row["global_reset_at"] = gr_at.isoformat() if gr_at else None
    return result


def quota_get_all_overrides() -> list[dict]:
    """Return all override rows with user display name."""
    with get_connection() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(
                """SELECT u.id AS user_id, u.ldap_username, u.display_name,
                          o.quota_type, o.limit_value
                   FROM user_quota_overrides o
                   JOIN users u ON u.id = o.user_id
                   ORDER BY u.display_name, o.quota_type"""
            )
            rows = cur.fetchall()
    return [dict(row) for row in rows]
