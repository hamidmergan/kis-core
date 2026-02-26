import json
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

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
    """Return True if the user has a pending/running/awaiting_user job for any of the given tools."""
    placeholders = ",".join("?" * len(tools))
    with get_connection() as conn:
        row = conn.execute(
            f"""SELECT 1 FROM jobs
               WHERE user_id = ? AND tool IN ({placeholders})
               AND status IN ('pending', 'running', 'awaiting_user')
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
                       started_at = COALESCE(started_at, ?)
                   WHERE job_uuid = ?""",
                (status, error_message, progress_json, now, job_uuid),
            )
        elif status in ("success", "failed"):
            conn.execute(
                """UPDATE jobs
                   SET status = ?, error_message = ?, progress = ?,
                       completed_at = ?
                   WHERE job_uuid = ?""",
                (status, error_message, progress_json, now, job_uuid),
            )
        else:
            conn.execute(
                """UPDATE jobs
                   SET status = ?, error_message = ?, progress = ?
                   WHERE job_uuid = ?""",
                (status, error_message, progress_json, job_uuid),
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
