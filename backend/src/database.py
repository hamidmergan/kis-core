import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

_TZ_BERLIN = ZoneInfo("Europe/Berlin")


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

# Per-tool-group limits for stored result files per user.
# When a new result is saved and the group limit is exceeded,
# the oldest file in that group is deleted from disk (DB record is kept).
MAX_RESULT_FILES = {
    "video": 1,   # video_dubbing, screencast_render, screencast_auto, screencast_demo_render
    "tts": 5,
    "other": 10,  # screencast_translate JSONs etc.
}

TOOL_RESULT_GROUP = {
    "video_dubbing": "video",
    "screencast_render": "video",
    "screencast_auto": "video",
    "screencast_demo_render": "video",
    "tts": "tts",
}

DB_PATH = Path("/app/data/database.db")


def get_connection() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(admin_email: Optional[str] = None) -> None:
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                ldap_username TEXT NOT NULL UNIQUE,
                display_name  TEXT NOT NULL,
                email         TEXT,
                active        INTEGER NOT NULL DEFAULT 1,
                created_at    TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)
        # Migration: add email column to existing databases
        try:
            conn.execute("ALTER TABLE users ADD COLUMN email TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists

        conn.execute("""
            CREATE TABLE IF NOT EXISTS whitelist (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                email      TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)

        # Migration: drop old jobs table if it has the old schema (stored_filename column)
        cols = {row[1] for row in conn.execute("PRAGMA table_info(jobs)").fetchall()}
        if cols and "stored_filename" in cols:
            conn.execute("DROP TABLE jobs")

        conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                job_uuid          TEXT NOT NULL UNIQUE,
                user_id           INTEGER NOT NULL DEFAULT 0,
                tool              TEXT NOT NULL,
                original_filename TEXT NOT NULL DEFAULT '',
                input_path        TEXT,
                result_path       TEXT,
                result_filename   TEXT,
                status            TEXT NOT NULL DEFAULT 'pending',
                error_message     TEXT,
                progress          TEXT,
                celery_task_id    TEXT,
                created_at        TEXT NOT NULL DEFAULT (datetime('now')),
                started_at        TEXT,
                completed_at      TEXT,
                expires_at        TEXT
            )
        """)
        # Migration: add celery_task_id column to existing databases
        try:
            conn.execute("ALTER TABLE jobs ADD COLUMN celery_task_id TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists
        try:
            conn.execute("ALTER TABLE jobs ADD COLUMN started_at TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists
        try:
            conn.execute("ALTER TABLE jobs ADD COLUMN completed_at TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists
        try:
            conn.execute("ALTER TABLE jobs ADD COLUMN progress_updated_at TEXT")
        except sqlite3.OperationalError:
            pass  # column already exists
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                key        TEXT NOT NULL UNIQUE,
                value      TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT (datetime('now'))
            )
        """)

        # Auto-whitelist admin email so first login works without manual DB edits
        if admin_email and admin_email.strip():
            conn.execute(
                "INSERT OR IGNORE INTO whitelist (email) VALUES (?)",
                (admin_email.strip().lower(),),
            )

        conn.commit()


# --- Users ---

def get_user_by_username(ldap_username: str):
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE ldap_username = ?", (ldap_username,)
        ).fetchone()


def get_user_by_id(user_id: int):
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM users WHERE id = ?", (user_id,)
        ).fetchone()


def create_user(ldap_username: str, display_name: str, email: str, active: int) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT INTO users (ldap_username, display_name, email, active) VALUES (?, ?, ?, ?)",
            (ldap_username, display_name, email, active),
        )
        conn.commit()
        return cur.lastrowid


def update_user(user_id: int, display_name: str, email: str, active: int) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE users SET display_name = ?, email = ?, active = ? WHERE id = ?",
            (display_name, email, active, user_id),
        )
        conn.commit()


# --- Whitelist ---

def get_whitelist_emails() -> list[str]:
    with get_connection() as conn:
        rows = conn.execute("SELECT email FROM whitelist ORDER BY created_at").fetchall()
        return [row["email"] for row in rows]


def add_to_whitelist(email: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO whitelist (email) VALUES (?)", (email.strip().lower(),)
        )
        conn.commit()


def remove_from_whitelist(email: str) -> None:
    with get_connection() as conn:
        conn.execute("DELETE FROM whitelist WHERE LOWER(email) = LOWER(?)", (email.strip(),))
        conn.commit()


def is_email_whitelisted(email: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT 1 FROM whitelist WHERE LOWER(email) = LOWER(?)", (email.strip(),)
        ).fetchone()
        return row is not None


# --- Settings (key/value store) ---

def get_setting(key: str, default: str = "") -> str:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default


def set_setting(key: str, value: str) -> None:
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO settings (key, value)
               VALUES (?, ?)
               ON CONFLICT(key) DO UPDATE
               SET value = excluded.value,
                   updated_at = datetime('now')""",
            (key, value),
        )
        conn.commit()


# --- Jobs ---

JOB_RETENTION_HOURS = 12


def create_job(
    job_uuid: str,
    user_id: int,
    tool: str,
    original_filename: str,
    input_path: str | None = None,
) -> None:
    expires_at = (
        datetime.now(timezone.utc) + timedelta(hours=JOB_RETENTION_HOURS)
    ).strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        conn.execute(
            """
            INSERT INTO jobs (job_uuid, user_id, tool, original_filename, input_path, expires_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (job_uuid, user_id, tool, original_filename, input_path, expires_at),
        )
        conn.commit()


def get_job(job_uuid: str):
    with get_connection() as conn:
        return conn.execute(
            "SELECT * FROM jobs WHERE job_uuid = ?", (job_uuid,)
        ).fetchone()


def get_jobs_by_user(user_id: int, limit: int = 20) -> list[dict]:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM jobs WHERE user_id = ? ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        ).fetchall()
        return [dict(row) for row in rows]


def set_job_celery_task_id(job_uuid: str, celery_task_id: str) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE jobs SET celery_task_id = ? WHERE job_uuid = ?",
            (celery_task_id, job_uuid),
        )
        conn.commit()


def delete_job(job_uuid: str) -> dict | None:
    """Delete a job record and return its file paths for cleanup."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT input_path, result_path, celery_task_id FROM jobs WHERE job_uuid = ?",
            (job_uuid,),
        ).fetchone()
        if not row:
            return None
        conn.execute("DELETE FROM jobs WHERE job_uuid = ?", (job_uuid,))
        conn.commit()
        return dict(row)


def has_active_job_for_tool(user_id: int, tools: list[str]) -> bool:
    """Return True if the user has a pending/running job for any of the given tools."""
    placeholders = ",".join("?" * len(tools))
    with get_connection() as conn:
        row = conn.execute(
            f"""SELECT 1 FROM jobs
               WHERE user_id = ? AND tool IN ({placeholders})
               AND status IN ('pending', 'running')
               LIMIT 1""",
            (user_id, *tools),
        ).fetchone()
        return row is not None


def get_results_for_tool_group(user_id: int, group: str) -> list[dict]:
    """Return all jobs with a result_path for the given tool group, ordered oldest first."""
    tools = [t for t, g in TOOL_RESULT_GROUP.items() if g == group]
    if not tools:
        return []
    placeholders = ",".join("?" * len(tools))
    with get_connection() as conn:
        rows = conn.execute(
            f"""SELECT id, result_path, result_filename, original_filename FROM jobs
               WHERE user_id = ? AND tool IN ({placeholders}) AND result_path IS NOT NULL
               ORDER BY created_at ASC""",
            (user_id, *tools),
        ).fetchall()
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
        conditions.append("(display_name LIKE ? OR ldap_username LIKE ? OR email LIKE ?)")
        params += [like, like, like]
    if date_from:
        conditions.append("created_at >= ?")
        params.append(_de_date_to_utc(date_from))
    if date_to:
        conditions.append("created_at <= ?")
        params.append(_de_date_to_utc(date_to, end_of_day=True))

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    with get_connection() as conn:
        rows = conn.execute(
            f"SELECT * FROM users {where} ORDER BY created_at DESC LIMIT ? OFFSET ?",
            params + [limit, offset],
        ).fetchall()
        total = conn.execute(
            f"SELECT COUNT(*) FROM users {where}",
            params,
        ).fetchone()[0]
    return [dict(row) for row in rows], total


def get_pending_users() -> list[dict]:
    """Users with active=0 (passed LDAP auth but not yet whitelisted)."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM users WHERE active = 0 ORDER BY created_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]


def activate_user(user_id: int) -> None:
    """Set active=1 for the given user."""
    with get_connection() as conn:
        conn.execute("UPDATE users SET active = 1 WHERE id = ?", (user_id,))
        conn.commit()


def deactivate_user_by_email(email: str) -> None:
    """Set active=0 for any user with the given email."""
    with get_connection() as conn:
        conn.execute("UPDATE users SET active = 0 WHERE LOWER(email) = LOWER(?)", (email.strip(),))
        conn.commit()


def get_all_jobs(
    limit: int = 50, offset: int = 0, q: str = "",
    date_from: str = "", date_to: str = "",
) -> tuple[list[dict], int]:
    """All jobs across all users, with display_name via JOIN, newest first.

    Returns (jobs, total_count).
    Filters: q (user/tool/filename), date_from/date_to (YYYY-MM-DD).
    """
    conditions = []
    params: list = []

    if q:
        like = f"%{q}%"
        conditions.append(
            "(u.display_name LIKE ? OR u.ldap_username LIKE ? OR j.tool LIKE ? OR j.original_filename LIKE ?)"
        )
        params += [like, like, like, like]
    if date_from:
        conditions.append("j.created_at >= ?")
        params.append(_de_date_to_utc(date_from))
    if date_to:
        conditions.append("j.created_at <= ?")
        params.append(_de_date_to_utc(date_to, end_of_day=True))

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    with get_connection() as conn:
        rows = conn.execute(
            f"""SELECT j.*, u.display_name AS user_display_name, u.ldap_username
               FROM jobs j
               LEFT JOIN users u ON j.user_id = u.id
               {where}
               ORDER BY j.created_at DESC
               LIMIT ? OFFSET ?""",
            params + [limit, offset],
        ).fetchall()
        total = conn.execute(
            f"""SELECT COUNT(*) FROM jobs j
               LEFT JOIN users u ON j.user_id = u.id
               {where}""",
            params,
        ).fetchone()[0]
    return [dict(row) for row in rows], total


def get_pending_dubbing_jobs() -> list[dict]:
    """Return all running dubbing jobs waiting for ElevenLabs (step='dubbing')."""
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT job_uuid, progress FROM jobs
               WHERE tool = 'video_dubbing'
               AND status = 'running'
               AND progress LIKE '%"step": "dubbing"%'"""
        ).fetchall()
        return [dict(row) for row in rows]


def update_job_status(
    job_uuid: str,
    status: str,
    error_message: str | None = None,
    progress: dict | None = None,
) -> None:
    progress_json = json.dumps(progress) if progress is not None else None
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        if status == "running":
            conn.execute(
                """UPDATE jobs
                   SET status = ?, error_message = ?, progress = ?,
                       progress_updated_at = ?,
                       started_at = COALESCE(started_at, ?)
                   WHERE job_uuid = ?""",
                (status, error_message, progress_json, now, now, job_uuid),
            )
        elif status in ("success", "failed"):
            conn.execute(
                """UPDATE jobs
                   SET status = ?, error_message = ?, progress = ?,
                       progress_updated_at = ?, completed_at = ?
                   WHERE job_uuid = ?""",
                (status, error_message, progress_json, now, now, job_uuid),
            )
        else:
            conn.execute(
                """UPDATE jobs
                   SET status = ?, error_message = ?, progress = ?,
                       progress_updated_at = ?
                   WHERE job_uuid = ?""",
                (status, error_message, progress_json, now, job_uuid),
            )
        conn.commit()


def update_job_result(
    job_uuid: str,
    result_path: str,
    result_filename: str,
) -> None:
    with get_connection() as conn:
        conn.execute(
            "UPDATE jobs SET result_path = ?, result_filename = ? WHERE job_uuid = ?",
            (result_path, result_filename, job_uuid),
        )
        conn.commit()

    # Evict oldest result files per tool group if user exceeds the group limit
    with get_connection() as conn:
        row = conn.execute(
            "SELECT user_id, tool FROM jobs WHERE job_uuid = ?", (job_uuid,)
        ).fetchone()
        if not row:
            return
        user_id = row["user_id"]
        tool = row["tool"]

    group = TOOL_RESULT_GROUP.get(tool, "other")
    limit = MAX_RESULT_FILES.get(group, MAX_RESULT_FILES["other"])
    old_jobs = get_results_for_tool_group(user_id, group) if group != "other" else []

    if group == "other":
        # For "other" (e.g. screencast_translate JSONs), use a simple global check
        with get_connection() as conn:
            other_tools = [t for t in TOOL_RESULT_GROUP] + ["screencast_translate"]
            placeholders = ",".join("?" * len(other_tools))
            old_jobs = conn.execute(
                f"""SELECT id, result_path FROM jobs
                   WHERE user_id = ? AND tool NOT IN ({placeholders})
                   AND result_path IS NOT NULL
                   ORDER BY created_at ASC""",
                (user_id, *other_tools),
            ).fetchall()
            old_jobs = [dict(r) for r in old_jobs]

    excess = len(old_jobs) - limit
    if excess > 0:
        with get_connection() as conn:
            for i in range(excess):
                old_path = old_jobs[i]["result_path"]
                if old_path:
                    Path(old_path).unlink(missing_ok=True)
                conn.execute(
                    "UPDATE jobs SET result_path = NULL, result_filename = NULL WHERE id = ?",
                    (old_jobs[i]["id"],),
                )
            conn.commit()


def get_stuck_running_jobs(threshold_minutes: int = 20) -> list[dict]:
    """Return running jobs whose progress_updated_at is older than threshold_minutes.

    These are candidates for being stuck (e.g. FFmpeg hung mid-render).
    """
    cutoff = (
        datetime.now(timezone.utc) - timedelta(minutes=threshold_minutes)
    ).strftime("%Y-%m-%d %H:%M:%S")
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT job_uuid, tool, progress, progress_updated_at FROM jobs
               WHERE status = 'running'
               AND progress_updated_at IS NOT NULL
               AND progress_updated_at <= ?""",
            (cutoff,),
        ).fetchall()
        return [dict(row) for row in rows]
